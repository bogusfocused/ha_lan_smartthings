"""Constants used by the SmartThings component and platforms."""

DOMAIN = "lan_smartthings"
SIGNAL_SMARTTHINGS_UPDATE = "lan_smartthings_update"
SIGNAL_SMARTAPP_PREFIX = "lan_smartthings_smartap_"
STORAGE_KEY = DOMAIN
CLASSIC_APP_NAME = "Home Assistant Relay"
CONF_LAN_CALLBACK_WEBHOOK_ID = "lan_webhook_id"
CONF_HUB_ACCESS_TOKEN = "hub_access_token"
CONF_HUB_URL = "hub_url"
CONF_HUB_IP = "hub_ip"
CONF_CLOUD_CALLBACK_WEBHOOK_ID = "cloud_webhook_id"
CONF_TARGET_URL_BASE = "target_url_base"
CONF_TARGET_URL = "target_url"
CONF_APP_ID = "app_id"
USER_AGENTv1 = "HA ST Link/1.0"

import importlib
proxy = importlib.import_module(".smartthings.const", __package__)
common = set(dir()) & set(dir(proxy))
for a in [a for a in common if not a.startswith('__')]:
    setattr(proxy, a, locals()[a])

from .smartthings.const import *
