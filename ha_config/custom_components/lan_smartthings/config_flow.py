"""Config flow to configure SmartThings."""
from .smartthings.config_flow import SmartThingsFlowHandler
import os
from .const import DOMAIN, CONF_APP_ID
import logging
from typing import Any, Callable, Coroutine, Dict, Optional, Protocol, TypeVar
import voluptuous as vol
from .const import CONF_LOCATION_ID
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.config_entries import HANDLERS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import DiscoveryInfoType
import re
from .hub import Hub
from .smartapp import _SmartApps, classic_smartapps

_LOGGER = logging.getLogger(__name__)

re_uuid = re.compile(r"^[0-F]{8}-([0-F]{4}-){3}[0-F]{12}$")


class ForwardProtocol(Protocol):

    @property
    def is_forwarding(self) -> bool:
        ...

    @property
    def user_input(self) -> Optional[Dict[str, Any]]:
        ...


StepMethod = TypeVar('StepMethod', bound=Callable[[Any, Optional[Dict[str, Any]]],
                                                  Coroutine[Any, Any, FlowResult]])

StepCall = Callable[[Optional[Dict[str, Any]]],
                    Coroutine[Any, Any, FlowResult]]


def forward(func: StepMethod):
    """Register decorated function."""
    name = func.__name__

    async def wrapper(self: ForwardProtocol, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if self.is_forwarding:
            meth = getattr(SmartThingsFlowHandler, name)
            return await meth(self, self.user_input)
        else:
            return await func(self, user_input)

    return wrapper


@HANDLERS.register(DOMAIN)
class LanSmartThingsFlowHandler(SmartThingsFlowHandler, ForwardProtocol):
    def __init__(self) -> None:
        super().__init__()
        self._is_forwarding: bool = False
        self._user_input: Optional[Dict[str, Any]] = None
        self.access_token: Optional[str] = None
        self._entry_point: Optional[StepCall] = None
        self.apps: Optional[_SmartApps] = None
        self.app_id: Optional[str] = None
        self.servername: Optional[str] = None

    @property
    def is_forwarding(self) -> bool:
        return self._is_forwarding

    @property
    def user_input(self) -> Optional[Dict[str, Any]]:
        return self._user_input

    @forward
    async def async_step_pat(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            self.access_token = self.access_token or os.environ.get("access_token")
            return self.async_show_form(
                step_id="pat",
                data_schema=vol.Schema(
                    {vol.Required(CONF_ACCESS_TOKEN,default=self.access_token): str}
                ),
                errors=errors,
                description_placeholders={
                    "token_url": "https://account.smartthings.com/tokens",
                    "component_url": "https://www.home-assistant.io/integrations/smartthings/",
                },
            )
        access_token = user_input[CONF_ACCESS_TOKEN]
        self.access_token = access_token
        try:
            self.apps = await classic_smartapps(
                async_get_clientsession(self.hass), access_token)
        except ValueError as exc:
            return self.async_abort(reason=str(exc))
        return await self.async_step_select_app()

    async def async_step_user(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """Get the Personal Access Token and validate it."""
        if self.is_forwarding:
            return await super().async_step_user({})
        else:
            self._entry_point = self.async_step_user
            return await self.async_step_pat()

    async def async_step_select_app(self, user_input=None):
        """Ask user to select the location to setup."""
        if user_input is None or CONF_APP_ID not in user_input:
            # Get available locations
            locations_options = {
                app["id"]: f'{app["label"]} @ {app["location"]["name"]}' for app in self.apps.apps}
            if len(locations_options) == 1:
                user_input = user_input or {}
                user_input[CONF_APP_ID] = list(locations_options.keys())[0]
            else:
                return self.async_show_form(
                    step_id="select_app",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_APP_ID): vol.In(locations_options)}
                    ),
            )

        self.app_id = user_input[CONF_APP_ID]
        app = [app for app in self.apps.apps if app["id"] == self.app_id][0]
        self.location_id = app["location"]["id"]
        self.servername = self.apps.servers[self.location_id]
        hub = await Hub.setup(hass=self.hass, app=app, servername=self.servername)
        return await self.forward()

    @forward
    async def async_step_select_location(self, user_input=None):
        pass
    
    @forward
    async def async_step_install(self, user_input=None):
        pass

    async def forward(self):
        self._is_forwarding = True
        self._user_input = {
            CONF_LOCATION_ID: self.location_id,
            CONF_ACCESS_TOKEN: self.access_token,
        }
        return await self._entry_point(self._user_input)

    async def async_step_zeroconf(self,
                                  discovery_info: DiscoveryInfoType
                                  ) -> FlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        async_dispatcher_send(
            self.hass, "smarthings_hub_found", discovery_info)
        return self.async_abort(reason="Hub found")
