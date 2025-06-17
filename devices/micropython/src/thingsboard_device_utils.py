import time
import network
import json
from umqtt.simple import MQTTClient


def network_connect():
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


def platform_client() -> MQTTClient:
    with open('thingsboard_config.json', 'r') as file:
        thingsboard_config = json.load(file)
    print(thingsboard_config)

    mqttClient = MQTTClient(client_id="umqtt_client",
        server=thingsboard_config['server_ip'],
        port=thingsboard_config['server_port'],
        user=thingsboard_config['device_access_token'],
        password=""
    )
    # mqttClient.connect()
    # print("Conected to Thingsboard platform")
    return mqttClient


def wait_until(t):
    wait_time = time.ticks_diff(t, time.ticks_ms())
    if wait_time > 0:
        time.sleep_ms(wait_time)


def get_firmware_info() -> dict:
    """Lee el sistema y devuelve la información del firmware"""
    info = {"title" : "mi_fw", "version" : "0.0.0"}
    return info
