import time
import network
import json
from umqtt.simple import MQTTClient
import random

#NETWORK_NAME = 'DIGIFIBRA-QFzA'
#NETWORK_PASSWORD = 'cFCE45CtEGkY'
#NETWORK_NAME = 'MOVISTAR_9CA0'
#NETWORK_PASSWORD = '7u34A7v4Ju4A4Wx7A977'


def do_connect():
    with open('wifi_config.json', 'r') as file:
        wifi_config = json.load(file)
    print(wifi_config)

    wlan = network.WLAN(network.WLAN.IF_STA)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(wifi_config['SSID'], wifi_config['password'])
        while not wlan.isconnected():
            print("Esperando a la conexión wifi...")
            time.sleep(1)
    print('Configuración de red:', wlan.ipconfig('addr4'))

do_connect()

with open('thingsboard_config.json', 'r') as file:
    thingsboard_config = json.load(file)
print(thingsboard_config)

mqttClient = MQTTClient(client_id="umqtt_client",
    server=thingsboard_config['server_ip'],
    port=thingsboard_config['server_port'],
    user=thingsboard_config['device_access_token'],
    password=""
)
mqttClient.connect()
print("Conected to Thingsboard platform")
random_value = random.randint(0,8)

mqttClient.publish(b"v1/devices/me/telemetry", b"""{"random_value":%d}""" % random_value)
#    ^
#    |
#    *-- equivalente a: mosquitto_pub -d -q 1 -h "YOUR_TB_HOST" -p "1883" \
#        -t "v1/devices/me/telemetry" -u "YOUR_ACCESS_TOKEN" -m {"temperature":245}

print("Mensaje enviado (valor %d)" % random_value)
