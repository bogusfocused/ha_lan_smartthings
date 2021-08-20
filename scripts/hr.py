"""Utility to clean up SmartApps created by the Home Assistant integration."""
import argparse
import asyncio
import os
import aiohttp
from pysmartthings import SmartThings



    # """Run the utility."""
    # parser = argparse.ArgumentParser("hass_smartthings_remove")
    # parser.add_argument("token", help="Your SmartThings Personal Access Token",
    #                     type=str)
    # args = parser.parse_args()



async def remove_apps(token: str):
    """Remove Home Assistant apps and installed apps."""
    async with aiohttp.ClientSession() as session:
        api = SmartThings(session, token)

        apps = await api.apps()
        installed_apps = await api.installed_apps()

        for app in apps:
            if not app.app_name.startswith('homeassistant.'):
                continue
            # Remove installed apps first
            for installed_app in installed_apps:
                if installed_app.app_id == app.app_id:
                    await api.delete_installed_app(
                        installed_app.installed_app_id)
                    print("Removed installed app '{}' ({})".format(
                        installed_app.display_name,
                        installed_app.installed_app_id))
            # Remove the app itself
            await api.delete_app(app.app_id)
            print("Removed app '{}' ({})".format(app.app_name, app.app_id))
            
            
loop = asyncio.get_event_loop()
loop.run_until_complete(remove_apps(os.environ.get("access_token")))
loop.close()
