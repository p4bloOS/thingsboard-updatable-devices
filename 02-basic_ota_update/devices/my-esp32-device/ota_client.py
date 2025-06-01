import random
import machine
import time
import gc
import json
from math import ceil
from hashlib import sha256
from umqtt.simple import MQTTClient
import thingsboard_device_utils as utils




def request_firmware_chunk():
    # Solicitud de un chunck de actualización
    mqtt_client.publish(f"v2/fw/request/{self.__firmware_request_id}/chunk/{self.__current_chunk}", payload=payload, qos=1)

def dummy_upgrade(version_from, version_to):
    print(f"Updating from {version_from} to {version_to}:")
    for x in range(5):
        sleep(1)
        print(20*(x+1),"%", sep="")
    print(f"Firmware is updated!\n Current firmware version is: {version_to}")


def generic_callback(topic, msg):
    print("Callback genérico:", topic, msg)

if __name__ == "__main__":



    utils.network_connect()
    mqtt_client: MQTTClient = utils.platform_client()

    request_id = 0
    updater = OTAUpdater(mqtt_client,
        chunk_size=200,
        request_id_a=request_id+1,
        request_id_b=request_id+2)

    def main_callback(topic, msg):
        generic_callback(topic, msg)
        updater.on_message_callback(topic, msg)

    mqtt_client.set_callback(main_callback)

    mqtt_client.connect()

    updater.prepare_for_ota()
    request_id = request_id + 1

    mqtt_client.subscribe(b"v1/devices/me/attributes")


    while True:
        mqtt_client.wait_msg()

    while True:
        time.sleep_ms(5000)
        print('Heap memory free:', gc.mem_free())
        print('Heap memory used:', gc.mem_alloc())
