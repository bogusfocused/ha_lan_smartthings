/**
 *  Home Assistant to smartthings Link smart app
 *
 *  Authors
     - Rohit <bogusfocused@gmail.com>
 *
 *  Copyright 2016
 *
 *  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 *  in compliance with the License. You may obtain a copy of the License at:
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 *  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License
 *  for the specific language governing permissions and limitations under the License.
 */
import groovy.transform.Field
import groovy.json.JsonBuilder

@Field CAPABILITIES = [
'capability.accelerationSensor',
'capability.airQualitySensor',
'capability.alarm',
'capability.battery',
'capability.beacon',
'capability.button',
'capability.carbonDioxideMeasurement',
'capability.carbonMonoxideDetector',
'capability.colorControl',
'capability.colorTemperature',
'capability.consumable',
'capability.contactSensor',
'capability.doorControl',
'capability.dustSensor',
'capability.energyMeter',
'capability.garageDoorControl',
'capability.illuminanceMeasurement',
'capability.imageCapture',
'capability.lock',
'capability.mediaController',
'capability.motionSensor',
'capability.musicPlayer',
'capability.pHMeasurement',
'capability.powerMeter',
'capability.presenceSensor',
'capability.relativeHumidityMeasurement',
'capability.relaySwitch',
'capability.shockSensor',
'capability.signalStrength',
'capability.sleepSensor',
'capability.smokeDetector',
'capability.soundSensor',
'capability.soundPressureLevel',
'capability.stepSensor',
'capability.switch',
'capability.switchLevel',
'capability.tamperAlert',
'capability.temperatureMeasurement',
'capability.thermostat',
'capability.thermostatCoolingSetpoint',
'capability.thermostatFanMode',
'capability.thermostatHeatingSetpoint',
'capability.thermostatMode',
'capability.thermostatOperatingState',
'capability.thermostatSetpoint',
'capability.threeAxis',
'capability.timedSession',
'capability.touchSensor',
'capability.ultravioletIndex',
'capability.valve',
'capability.voltageMeasurement',
'capability.waterSensor',
'capability.windowShade'
]

definition(
    name: 'Home Assistant Relay', //Do not change the name. HA finds app by name.
    namespace: 'bogusfocused',
    author: 'Rohit',
    description: 'Home Assistant to smartthings Link smart app',
    category: 'My Apps',
    iconUrl: 'https://s3.amazonaws.com/smartapp-icons/Connections/Cat-Connections.png',
    iconX2Url: 'https://s3.amazonaws.com/smartapp-icons/Connections/Cat-Connections@2x.png',
    iconX3Url: 'https://s3.amazonaws.com/smartapp-icons/Connections/Cat-Connections@3x.png',
    singleInstance: true
)
mappings {
	path("/relay") {
		action: [
			POST: "relay_post"
		]
	}
	
}
preferences {
    section ('Input') {
        CAPABILITIES.collect { cap ->
            input cap.drop(11), cap, title: cap.drop(11).replaceAll(/([A-Z])/) { all, c-> " ${c}" }.capitalize(), multiple: true, required: false, hideWhenEmpty: true
        }
    }
    section() {
    	paragraph "Events receive from cloud are forwarded to Home Assistant. You can enable or disable it. Events captured on LAN are always forwarded."
    	input "forward_events", "bool", title: "Forward", defaultValue: true, required: true
    }
    
}

def installed() {
  log.debug "Installed with settings: ${settings}"
  initialize()
}

def updated() {
  log.debug "Updated with settings: ${settings}"
  // Unsubscribe from all events
  unsubscribe()
  unschedule()
  // Subscribe to stuff
  initialize()

}
def getDevices()
{
	def devices = [:]
    CAPABILITIES.each { cap -> 
    			def devs = settings[cap.drop(11)]
                if(devs != null) devices = devices + devs.collectEntries { device -> [device.id,device] };
                }
    //log.debug devices
    return devices
}

def initialize() {
    def hub = location.hubs[0]
    log.debug "Hub listening on: ${hub.localIP}:${hub.localSrvPortTCP}"
    subscribe(location,null, lanEventHandler, [filterEvents: false])
    if(state.host != null) register();
}

def lanEventHandler(evt)
{
	def msg = parseLanMessage(evt.description)
  //log.debug msg
  if (msg.header?.contains("HA ST Link/1.0") && msg.header?.startsWith('POST ')) 
  {
    def data = msg.json
    switch(msg.headers.Action)
    {
    case "register":
      state.host = data.host
      state.path = data.path
      state.forward_path = data.forward_path
      register()
      break;
    case "command":
      def cmd = data.command
      device = getDevices()[data.device_id]
      if (data.args == null) device?."$cmd"()
      else device?."$cmd"(data.args)
      break;
    case "unregister":          
      unsubscribe("handleEvt")
      state.host = null
      state.path = null
      state.forward_path = null
      break;
    }
  }
}

def register()
{
  log.debug "Registered HA Instance from ${state.host}${state.path} with forwarding to ${state.forward_path}"
  if (!state.accessToken) {createAccessToken()}   
  postData(state.host,state.path,[accessToken: state.accessToken])
  // Subscribe to all events from devices
  unsubscribe("handleEvt")
  getDevices().each { id,device  ->
          device.supportedAttributes.each { attribute ->
            subscribe(device, attribute.name, handleEvt)
              }
          }
}

def handleEvt(evt)
{
	try{
        if("${evt.source}" != "DEVICE") return;
        if("${state.lastEventId}" == "${evt.id}") return;
        def data = [
            eventId: evt.id,
            locationId:evt.locationId,
            deviceId: evt.deviceId,
            attribute:evt.name,
            value: evt.device?.currentValue(evt.name),
            data: evt.data,
            stateChange: evt.isStateChange()
        ]
        postData(state.host, state.path,[event: data])
        state.lastEventId = "${evt.id}"
        log.debug "Sent event captured on LAN id:${state.lastEventId}"
	}
 	catch (e) {
    	log.debug "something went wrong: $e"
	}
}

def relay_post()
{
	//log.debug "Got request to relay: ${request?.JSON?.lifecycle}"
	def j = request?.JSON
    if(j == null) return;
    //log.debug j
	switch(j.lifecycle)
    {
    case "EVENT":
        if(settings.forward_events){
        	def evtid = j?.eventData?.events[0]?.deviceEvent?.eventId
            if(evtid == null || "${state.lastEventId}" != "${evtid}")
            {
            	postData(state.host,state.forward_path,j)
        		state.lastEventId = "${evtid}"
            }
           }
        render data: '''{ "eventData": {} }'''
        break
	case "PING":
    	postData(state.host,state.forward_path,j)
		def p = j.pingData
		render data: new JsonBuilder([pingData:p]).toPrettyString()
        break
 	case "CONFIRMATION":
    	postData(state.host,state.forward_path,j)
		render data: new JsonBuilder([targetUrl:state.url]).toPrettyString()
        break
 	case "INSTALL":
    	postData(state.host,state.forward_path,j)
   		render data: '''{ "installData": {} }'''
        break
	case "UNINSTALL":
    	postData(state.host,state.forward_path,j)
   		render data: '''{ "uninstallData": {} }'''
        break
	case "UPDATE":
    	postData(state.host,state.forward_path,j)
   		render data: '''{ "updateData": {} }'''
        break
 	case "CONFIGURATION":
    	postData(state.host,state.forward_path,j)
 		def data = j.configurationData
        switch(data.phase) 
        {
        case "INITIALIZE":
             render data: '''
             {
                "configurationData": {
                  "initialize": {
                    "name": "Home Assistant",
                    "description": "Home at hub",
                    "id": "app",
                    "permissions": ["r:devices:*"],
                    "firstPageId": "1"
                  }
                }
              }
              '''
               break
		case "PAGE":
             render data: '''
             {
                "configurationData": {
                  "page": {
                    "pageId": "1",
                    "name": "Configuration",
                    "nextPageId": null,
                    "previousPageId": null,
                    "complete": true,
                    "sections": []
                  }
                }
              }
              '''
            break
       } // phase switch
       break
    default:
    	postData(state.host,state.forward_path,j)
        render data: null
        break;
 	} // lifecycle switch

}

def postData(host,path,body)
{
	if(path == null || host == null) return;
    def headers = [:]
    headers.put('HOST', host)
    headers.put('Content-Type', 'application/json')
    def params = [
        method: 'POST',
        path: path,
        headers: headers,
        body: body
     ]
    //log.debug "Posting ${params}"
    def hubAction = new physicalgraph.device.HubAction(params)
    sendHubCommand(hubAction)
  }
