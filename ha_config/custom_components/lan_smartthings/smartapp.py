"""SmartApp functionality to receive cloud-push notifications."""
from .const import CLASSIC_APP_NAME, CONF_TARGET_URL, DOMAIN
from .smartthings.const import DATA_MANAGER
from .smartthings.smartapp import *
from typing import Any, Dict, List, Tuple
import logging
from homeassistant.core import HomeAssistant
from aiohttp.client import ClientSession,ClientRequest
import aiohttp.web as web
from pysmartapp.smartapp import SmartAppManager
from .hub import _AppInfo, _SmartApps
import re
_LOGGER = logging.getLogger(__name__)


class Error(Exception):
    pass


class ApplicationNotFoundError(Error):
    pass


PATTERN = r'\"https:\/\/([^\.]*)\.api\.smartthings\.com:443\/location\/installedSmartApps\/([-a-f0-9]*)\"'

PAT = r'<td>.*href="\/installedSmartApp\/show\/([-a-f0-9]*)"[^>]*>(.*)[^<]<.*<\/td>\s*<td>(.*)<\/td>\s*<td>(.*)<\/td>\s*<td>.*href="\/location\/show\/([-a-f0-9]*)".*<\/td>'

INSTALATIONS = "https://{servername}.api.smartthings.com:443/api/smartapps/installations"
INSTALATION_STATE = "https://{servername}.api.smartthings.com:443/installedSmartApp/showModal/{appid}"
INSTALL_STATE_PATTERN = re.compile(r'.*(?<=<h4>Application State<\/h4>)(.*)', re.DOTALL)
STATE_BODY = re.compile('.*(?<=<tbody>)(.*)(?=<\\/tbody>).*', re.DOTALL)
PROP_PATTERN =  re.compile(r'<tr>\s*<td>(.*?)<\/td>\s*<td>(.*?)<\/td>\s*<\/tr>', re.DOTALL)

async def classic_smartapps(session: ClientSession, access_token: str) -> _SmartApps:
    async with session.request(
        "GET", "https://graph.api.smartthings.com/location/list",
        headers={"Authorization": "Bearer " + access_token},
    ) as resp:
        html = await resp.text()
    matches: List[Tuple[str, str]] = re.findall(PATTERN, html)
    if not matches:
        raise ValueError("no_available_locations")
    loc_server_map = {l: s for s, l in matches}
    servers = {*loc_server_map.values()}
    classic_apps: List[_AppInfo] = []
    for servername in servers:
        async with session.request(
            "GET", INSTALATIONS.format_map({"servername": servername}),
            headers={"Authorization": "Bearer " + access_token},
        ) as resp:
            apps = await resp.json()
            myapps: List[_AppInfo] = [app for app in apps if app["smartAppVersion"]
                                      ["name"] == CLASSIC_APP_NAME]

            classic_apps.extend(myapps)
    if not classic_apps:
        raise ValueError("classic_smartapp_not_installed")
    properties: Dict[str, Dict[str, str]] = {}
    for capps in classic_apps:
        async with session.request(
            "GET", INSTALATION_STATE.format_map(
                {"servername": servername, "appid": capps["id"]}),
            headers={"Authorization": "Bearer " + access_token},
        ) as resp:
            html = await resp.text()
        try:
            app_state = PROP_PATTERN.findall(STATE_BODY.match(INSTALL_STATE_PATTERN.match(html)[1])[1])
            props = {k: v for k, v in app_state}
            properties[capps["id"]] = props
        except:
            pass
    return _SmartApps(classic_apps, loc_server_map, properties)


def _validate_webhook_requirements(*args, **kwargs) -> bool:
    '''suppress validation of webhook as we are not going to use it.'''
    return True

validate_webhook_requirements = _validate_webhook_requirements

async def _smartapp_webhook(hass: HomeAssistant, webhook_id: str, request : ClientRequest):
    """
    Handle a smartapp lifecycle event callback from SmartThings.

    Requests from SmartThings are digitally signed and the SmartAppManager
    validates the signature for authenticity.
    """
    manager : SmartAppManager = hass.data[DOMAIN][DATA_MANAGER]
    data = await request.json()
    result = await manager.handle_request(data, request.headers, validate_signature=False)
    return web.json_response(result)

smartapp_webhook = _smartapp_webhook

get_webhook_url = lambda hass: hass.data.get(DOMAIN,{}).get(CONF_TARGET_URL,None)
