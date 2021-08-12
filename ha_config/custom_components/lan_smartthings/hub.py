"""SmartApp functionality to receive cloud-push notifications."""
import asyncio
import logging
import sys
from typing import Any, Callable, Coroutine, Dict, Generic, List, Mapping, NamedTuple, Optional, TypeVar, TypedDict, cast
from uuid import uuid4

from aiohttp import hdrs
from aiohttp.client import ClientTimeout
from aiohttp.web import Request
from pysmartthings.app import APP_TYPE_WEBHOOK, CLASSIFICATION_AUTOMATION
from .smartthings.const import APP_NAME_PREFIX, CONF_CLOUDHOOK_URL, CONF_INSTANCE_ID
from homeassistant.components.network.util import async_get_source_ip
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from pysmartapp.const import EVENT_TYPE_DEVICE
from pysmartapp.event import EventRequest
import homeassistant.components.webhook as webhook
from .const import (CONF_CLOUD_CALLBACK_WEBHOOK_ID, CONF_HUB_ACCESS_TOKEN, CONF_HUB_IP, CONF_HUB_URL, CONF_LAN_CALLBACK_WEBHOOK_ID, CONF_TARGET_URL, CONF_TARGET_URL_BASE, DOMAIN, STORAGE_KEY, STORAGE_VERSION,  # type: ignore
                    USER_AGENTv1)

BrokerHandler = Callable[[EventRequest], Coroutine[Any, Any, None]]
_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class _HubData(TypedDict):
    localIP: str
    localSrvPortTCP: str
    macAddress: str  # 28:7F....


class _Hub(TypedDict):
    data: _HubData
    id: str
    name: str


class _Location(TypedDict):
    id: str
    name: str
    hubs: List[_Hub]


class _SmartAppVersion(TypedDict):
    author: str
    version: str
    id: str
    name: str
    installedCount: int


class _AppInfo(TypedDict):
    id: str
    label: str
    location: _Location
    smartAppVersion: _SmartAppVersion


class _SmartApps(NamedTuple):
    apps: List[_AppInfo]
    servers: Mapping[str, str]
    properties: Mapping[str, Mapping[str, str]]


class HubInfo():

    def __init__(self, *, hass: HomeAssistant,
                 lan_webhook_id: str,
                 hub_url: str,
                 hub_ip: str, targeturl_base: str,
                 cloud_webhook_id: str,
                 access_token: str,
                 instance_id: str,
                 **_):
        self.hass = hass
        self._instance_id = instance_id
        self._hub_ip = hub_ip
        self._targeturl_base = targeturl_base
        self._hub_url = hub_url
        self._lan_webhook_id = lan_webhook_id
        self._lan_callback_path = webhook.async_generate_path(lan_webhook_id)
        self._cloud_webhook_id = cloud_webhook_id
        self._cloud_callback_path = webhook.async_generate_path(
            cloud_webhook_id)
        self._access_token = access_token
        self._target_url = targeturl_base + access_token

    async def save(self):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        local_hub = {
            CONF_LAN_CALLBACK_WEBHOOK_ID: self._lan_webhook_id,
            CONF_HUB_ACCESS_TOKEN: self._access_token,
            CONF_CLOUD_CALLBACK_WEBHOOK_ID: self._cloud_webhook_id,
            CONF_HUB_URL: self._hub_url,
            CONF_HUB_IP: self._hub_ip,
            CONF_TARGET_URL_BASE: self._targeturl_base,
            CONF_INSTANCE_ID: self._instance_id,
            CONF_WEBHOOK_ID: self._cloud_webhook_id,
            CONF_CLOUDHOOK_URL: None,
        }
        await store.async_save(local_hub)

    @classmethod
    async def load(cls, hass: HomeAssistant):
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        local_hub = await store.async_load()
        info = HubInfo(hass=hass,
                       lan_webhook_id=local_hub[CONF_LAN_CALLBACK_WEBHOOK_ID],
                       access_token=local_hub[CONF_HUB_ACCESS_TOKEN],
                       cloud_webhook_id=local_hub[CONF_CLOUD_CALLBACK_WEBHOOK_ID],
                       hub_url=local_hub[CONF_HUB_URL],
                       hub_ip=local_hub[CONF_HUB_IP],
                       targeturl_base=local_hub[CONF_TARGET_URL_BASE],
                       instance_id=local_hub[CONF_INSTANCE_ID],
                       )

        return info


class Hub():

    def __init__(self, hass: HomeAssistant, *,
                 lan_host: str, info: HubInfo) -> None:
        self.hass = hass
        self._info = info
        self._lan_host = lan_host
        self._setup_done: bool = False
        self._last_event_id: Optional[str] = None
        self._broker_event_handler: Optional[BrokerHandler] = None
        self._installed_app_id: Optional[str] = None

    async def start(self, handler: BrokerHandler, installed_app_id: str):
        info = self._info
        if self._broker_event_handler:
            # skip because already started
            return
        self._broker_event_handler = handler
        self._installed_app_id = installed_app_id
        webhook.async_register(self.hass, DOMAIN, "SmartApp",
                               info._lan_webhook_id, self.webhook_handler)

    async def stop(self):
        webhook.async_unregister(self.hass, self._info._lan_webhook_id)
        self._broker_event_handler = None
        self._installed_app_id = None
        await self.post(action="unregister")

    @classmethod
    async def load(cls, *, hass: HomeAssistant):
        '''load the info from store'''
        info = await HubInfo.load(hass)
        access_token, lan_host = await cls._register(
            hass, lan_webhook_id=info._lan_webhook_id, cloud_webhook_id=info._cloud_callback_path,
            hub_url=info._hub_url, hub_ip=info._hub_ip)
        if info._access_token != access_token:
            info._access_token = access_token
            await info.save()
        ret = cls(hass, info=info, lan_host=lan_host)
        ret.patch_methods()       
        return ret

    @classmethod
    async def setup(cls, *, hass: HomeAssistant, app: _AppInfo, servername: str):
        '''Create the info and save it'''
        lan_webhook_id = webhook.async_generate_id()
        cloud_webhook_id = webhook.async_generate_id()
        hub_data = app["location"]["hubs"][0]["data"]
        hub_ip = hub_data["localIP"]
        port = hub_data["localSrvPortTCP"]
        hub_url = f"http://{hub_ip}:{port}"
        instance_id = str(uuid4())
        targeturl_base = f'https://{servername}.api.smartthings.com:443/api/smartapps/installations/{app["id"]}/relay?access_token='
        access_token, lan_host = await cls._register(hass, lan_webhook_id=lan_webhook_id, hub_url=hub_url, hub_ip=hub_ip, cloud_webhook_id=cloud_webhook_id)
        info = HubInfo(hass=hass, lan_webhook_id=lan_webhook_id,
                       hub_ip=hub_ip, hub_url=hub_url,
                       access_token=access_token,
                       targeturl_base=targeturl_base, cloud_webhook_id=cloud_webhook_id, instance_id=instance_id)
        await info.save()
        ret = cls(hass, info=info, lan_host=lan_host)
        ret.patch_methods()
        return ret

    def patch_methods(self):
        smartapp = sys.modules['custom_components.lan_smartthings.smartthings.smartapp']
        def patched_get_app_template(hass: HomeAssistant):
            return {
                    "app_name": APP_NAME_PREFIX + str(uuid4()),
                    "display_name": "Home Assistant",
                    "description": f"{hass.config.location_name} at {self.targeturl}",
                    "webhook_target_url": self.targeturl,
                    "app_type": APP_TYPE_WEBHOOK,
                    "single_instance": True,
                    "classifications": [CLASSIFICATION_AUTOMATION],
                }
        smartapp._get_app_template = patched_get_app_template
        smartapp.get_webhook_url = lambda hass: self.targeturl

    @classmethod
    async def _register(cls, hass: HomeAssistant, *, lan_webhook_id: str, hub_url: str, hub_ip: str, cloud_webhook_id: str):
        registration = hass.loop.create_future()

        async def handler(hass: HomeAssistant, webhook_id: str, request: Request):
            req = await request.json()
            if "accessToken" in req:
                access_token = req["accessToken"]
                if not registration.done():
                    registration.set_result(access_token)
        try:
            source_ip = async_get_source_ip(hub_ip)
            if not source_ip:
                raise ValueError("Cannot find ip address")
            lan_host = f"{source_ip}:{hass.http.server_port}"
            # Register webhook
            webhook.async_register(
                hass, DOMAIN, "SmartApp", lan_webhook_id, handler)
            await cls._post(
                hass=hass, action="register", url=hub_url,
                data={
                    "host": lan_host,
                    "path": webhook.async_generate_path(lan_webhook_id),
                    "forward_path": webhook.async_generate_path(cloud_webhook_id),
                }
            )
            await asyncio.wait_for(registration, 30)
            access_token = registration.result()
            webhook.async_unregister(hass, lan_webhook_id)
            return access_token, lan_host
        finally:
            webhook.async_unregister(hass, lan_webhook_id)

    async def execute_command(self, device_id: str, command: str, args: Any):
        await self.post("command", {"command": command,
                                    "device_id": device_id, "args": args})

    @property
    def targeturl(self):
        return self._info._target_url

    @property
    def cloud_webhook_id(self):
        return self._info._cloud_webhook_id

    async def _handle_lan_event(self, data):
        if not "event" in data:
            return
        json_data = data['event']
        event_id = json_data["eventId"]
        if self._last_event_id == event_id:  # ignore duplicate event
            return
        self._last_event_id = event_id
        req = EventRequest({
            'lifecycle': "",
            'executionId': "",
            'locale': "",
            'version': "",
            'settings': "",
            "eventData": {
                "authToken": "",
                "installedApp": {
                        'installedAppId': self._installed_app_id,
                        'locationId': json_data["locationId"],
                        'config': "",
                },
                "events": [
                    {
                        'eventType': EVENT_TYPE_DEVICE,
                        "deviceEvent": {
                            'subscriptionName': "",
                            'eventId': json_data["eventId"],
                            'locationId': json_data["locationId"],
                            'deviceId': json_data["deviceId"],
                            'componentId': "main",
                            'capability': "",
                            'attribute': json_data["attribute"],
                            'value': json_data["value"],
                            'valueType': "",
                            'data': json_data["data"],
                            'stateChange': json_data["stateChange"]
                        },

                    }],
            },
        })
        handler = self._broker_event_handler
        if not handler:
            raise ValueError("Handler is unexpectedly None")
        await handler(req)

    async def webhook_handler(self, hass: HomeAssistant, webhook_id: str, request: Request):
        req = await request.json()
        await self._handle_lan_event(req)

    async def post(self, action: str, data: Any = None):
        info = self._info
        hub_url = cast(str, info._hub_url)
        await self._post(hass=self.hass, url=hub_url, action=action, data=data)

    @staticmethod
    async def _post(*, hass: HomeAssistant, url: str, action: str, data: Any = None):
        to = ClientTimeout(total=5.0)
        session = async_get_clientsession(hass)
        headers = {hdrs.USER_AGENT: USER_AGENTv1, "Action": action}
        attempt = 0
        max_attempt = 5
        while attempt < max_attempt:
            try:
                async with session.request("POST", url, headers=headers, json=data,timeout=to) as resp:
                    result = await resp.text()
                    return
            except asyncio.TimeoutError:
                attempt+=1
                await asyncio.sleep(2)
            except Exception as exc:
                _LOGGER.error(exc)
                raise
