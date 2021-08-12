"""SmartApp functionality to receive cloud-push notifications."""
from .const import CLASSIC_APP_NAME, CONF_TARGET_URL, DOMAIN
from .smartthings.const import DATA_MANAGER
from .smartthings.smartapp import *
import sys
from typing import Any, Dict, List, Tuple
import logging
from homeassistant.core import HomeAssistant
from aiohttp.client import ClientSession, ClientRequest
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
INSTALL_STATE_PATTERN = re.compile(
    r'.*(?<=<h4>Application State<\/h4>)(.*)', re.DOTALL)
STATE_BODY = re.compile('.*(?<=<tbody>)(.*)(?=<\\/tbody>).*', re.DOTALL)
PROP_PATTERN = re.compile(
    r'<tr>\s*<td>(.*?)<\/td>\s*<td>(.*?)<\/td>\s*<\/tr>', re.DOTALL)


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
            app_state = PROP_PATTERN.findall(STATE_BODY.match(
                INSTALL_STATE_PATTERN.match(html)[1])[1])
            props = {k: v for k, v in app_state}
            properties[capps["id"]] = props
        except:
            pass
    return _SmartApps(classic_apps, loc_server_map, properties)

validate_webhook_requirements = lambda *args, **kwargs: True

_handle_request = SmartAppManager.handle_request 
async def handle_request(self, data: dict, headers: dict = None,
                            validate_signature: bool = True) -> dict:
        return await _handle_request(self,data,headers,validate_signature=False)

SmartAppManager.handle_request  = handle_request
