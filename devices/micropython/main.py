import time
import network
import json
from umqtt.simple import MQTTClient
import random
import machine



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


def platform_connect():
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
    return mqttClient


def publish_random_value(mqttClient):
    random_value = random.randint(0,8)
    mqttClient.publish(b"v1/devices/me/telemetry", b"""{"random_value":%d}""" % random_value)
    #    ^
    #    |
    #    *-- equivalente a: mosquitto_pub -d -q 1 -h "YOUR_TB_HOST" -p "1883" \
    #        -t "v1/devices/me/telemetry" -u "YOUR_ACCESS_TOKEN" -m {"temperature":245}
    print("Mensaje enviado (valor %d)" % random_value)


def wait_until(t):
    wait_time = time.ticks_diff(t, time.ticks_ms())
    if wait_time > 0:
        time.sleep_ms(wait_time)


if __name__ == "__main__":
    led_pin = machine.Pin(2, machine.Pin.OUT)
    led_pin.off()
    network_connect()
    mqtt_client = platform_connect()

    while True:
        current_time = time.ticks_ms()
        next_time = time.ticks_add(current_time, 5000)

        publish_random_value(mqtt_client)

        # Led signal
        led_pin.on()
        time.sleep_ms(500)
        led_pin.off()

        wait_until(next_time)
