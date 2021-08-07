import sys
from .package_finder import RedirectPackageFinder
sys.meta_path.insert(0, RedirectPackageFinder())
from .const import DOMAIN
from .smartthings.const import CONF_INSTALLED_APP_ID

# load const first to get it renamed
from .const import DOMAIN, DATA_BROKERS
from .smartthings import (async_setup as origin_async_setup,
                          async_setup_entry as origin_async_setup_entry,
                          async_remove_entry as origin_async_remove_entry,
                          async_unload_entry as origin_async_unload_entry,
                          async_migrate_entry as origin_async_migrate_entry,
                          )
from .smartthings import DeviceBroker
from pysmartthings import DeviceEntity
from .hub import Hub
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
_LOGGER = logging.getLogger(__name__)


def command(hub: Hub):
    async def wrapper(self: DeviceEntity, component_id: str, capability, command, args=None) -> bool:
        """Execute a command on the device."""
        await hub.execute_command(self.device_id, command, args)
        return True

    return wrapper


def sm_found(discovery_info):
    _LOGGER.debug(discovery_info)


async def async_setup(hass, config):
    #async_dispatcher_connect(hass, "smarthings_hub_found", sm_found)
    return await origin_async_setup(hass, config)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return_value = await origin_async_setup_entry(hass, entry)
    broker: DeviceBroker = hass.data[DOMAIN][DATA_BROKERS][entry.entry_id]
    hub = await Hub.load(hass=hass)
    DeviceEntity.command = command(hub)
    setattr(broker, "_hub", hub)
    await hub.start(lambda x: broker._event_handler(x, None, None), entry.data[CONF_INSTALLED_APP_ID])
    return return_value


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    return await origin_async_remove_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    broker: DeviceBroker = hass.data[DOMAIN][DATA_BROKERS][entry.entry_id]
    hub: Hub = getattr(broker, "_hub", None)
    if hub:
        await hub.stop()
    return await origin_async_unload_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await origin_async_migrate_entry(hass, entry)
