
# Smartthings on LAN for Home Assistant



## About Smartthings on LAN

This is a [Home Assistant](https://www.home-assistant.io/) integration of [SmartThings](https://www.smartthings.com/). If you do not use both, this is of no use to you. This code uses the standard builtin smartthings but tweaks a bit to remove requirement of incoming webhooks. Secure incoming webhooks are difficult to setup. The requirement also eliminates need for Duck DNS and nginx addons. 

Further it sends commands and recieve events on LAN. This makes it faster and more resilient of internet connection. It recieves events from cloud as well but forwards the first recieved (typically LAN) and discards the duplicates.

## Installation
A classic SmartApp on SmartThings hub and custom integration on Home Assistant will be installed.
<br/>

### Create Classic smartapp on Smartthings

 -  Login to the IDE at [https://account.smartthings.com](https://account.smartthings.com)   
   (create a Samsung Account one if you don't have one)'

- Click `My Locations` link and then select the location to install  SmartApp. 
  
- Click `My SmartApps` link
  >:warning: If you click  `My SmartApps` before selecting location, it will not work.
  
-  Click `New SmartApp` button and select `From Code` tab

-  Copy and paste the entire code of [smartapp.groovy](https://github.com/bogusfocused/ha_lan_smartthings/blob/main/smartapp.groovy) file. 
   >:zap: One way is to open the [raw content](https://raw.githubusercontent.com/bogusfocused/ha_lan_smartthings/main/smartapp.groovy), select all (Ctrl+A), copy (Ctrl+C) and paste (Ctrl+V)
 
- Click `Create` button. This will create the app.

- Click `App Settings` button
  
- Select `OAuth` and `Enable OAuth in Smart App`
  
- Click `Update` button. Ignore client id and client secret. We will not need them.

- Click `Code` button and then `Publish` -> `For Me` 
  

### Install the created SmartApp.

- Login at [https://my.smartthings.com](https://my.smartthings.com/)
  
- Click on the :heavy_plus_sign: sign and select `Add Groovy SmartApp`

- From the list select `Home Assistant Relay`

- You will now see a page to select devices. Select all devices in each category. Any devices left here will not work on LAN though it will work from cloud.
  
- You should see if everything went successfully.
   
               Success!
      You can close this window now.
  
- You can close the windows 


### Install Custom component in Home Assistant

- Copy `custom_components\ha_lan_smartthings` into your Home Assistant config folder.




## Licensing

Source code in this repository is copyright myself and
contributors, and licensed under the MIT License.

This software is available under the MIT License

See the [LICENSE](LICENSE) file for details.
