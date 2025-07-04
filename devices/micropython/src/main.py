import time
import machine
import random
import json

import sys
import lib.umqtt
sys.modules['umqtt']=lib.umqtt

from tb_device_mqtt import TBDeviceMqttClient

import utils


# Thingsboard MQTT client
client = utils.get_thingsboard_client()


def publish_random_value():
    """
    Envía a la plataforma un dato de telemetría con clave "random_value" y como
    valor un entero aleatorio entre 0 y 8.
    """
    random_value = random.randint(0,8)
    telemetry = {"random_value" : random_value}
    client.send_telemetry(telemetry)
    print("Telemtría enviada enviada: %s)" % json.dumps(telemetry))


if __name__ == "__main__":

    utils.network_connect()
    client.connect()

    led_pin = machine.Pin(2, machine.Pin.OUT)
    led_pin.off()


    while True:
        current_time = time.ticks_ms()
        next_time = time.ticks_add(current_time, 5000)

        publish_random_value()

        # Led signal
        led_pin.on()
        time.sleep_ms(5000)
        led_pin.off()

        utils.wait_until(next_time)
