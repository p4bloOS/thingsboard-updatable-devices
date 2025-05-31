import random
import machine
import time
import gc
import json
from math import ceil
from hashlib import sha256
from umqtt.simple import MQTTClient
import thingsboard_device_utils as utils

class OTAUpdater:

    # Shared attributes que la plataforma actualiza para solicitar una OTA
    FW_CHECKSUM_ATTR = "fw_checksum"
    FW_CHECKSUM_ALG_ATTR = "fw_checksum_algorithm"
    FW_SIZE_ATTR = "fw_size"
    FW_TITLE_ATTR = "fw_title"
    FW_VERSION_ATTR = "fw_version"
    FW_STATE_ATTR = "fw_state"
    REQUIRED_SHARED_KEYS = (f'{FW_CHECKSUM_ATTR},{FW_CHECKSUM_ALG_ATTR},{FW_SIZE_ATTR},{FW_TITLE_ATTR},{FW_VERSION_ATTR}')

    # Update States
    DOWNLOADING_ST = "DOWNLOADING"
    DOWNLOADED_ST = "DOWNLOADED"
    VERIFIED_ST = "VERIFIED"
    UPDATING_ST = "UPDATING"
    UPDATED_ST = "UPDATED"
    FAILED_ST = "FAILED"


    def _report_state(self, state: str):
        msg = json.dumps({
            "current_fw_title": self.current_fw_title,
            "current_fw_version": self.current_fw_version,
            "fw_state": state
        }).encode('utf-8')
        self.mqtt_client.publish("v1/devices/me/telemetry", msg)

    def __init__(self, mqtt_client, chunk_size, request_id_a, request_id_b):
        fw_info = utils.get_firmware_info()
        self.current_fw_title = fw_info['title']
        self.current_fw_version = fw_info['version']
        self.mqtt_client = mqtt_client
        self.request_id_attrs = request_id_a
        self.request_id_firmware = request_id_b
        self.firmware_data = b''
        self.chunk_size = chunk_size
        self.expected_chunk = -1

    def _verify_checksum(self):
        return True

    def on_message_callback(self, topic, msg):
        fw_notification_topic = b"v1/devices/me/attributes/response/%d" % self.request_id_attrs
        fw_chunk_topic = b"v2/fw/response/%d/chunk/%d" % (self.request_id_firmware, self.expected_chunk)

        if topic == fw_notification_topic:
            fw_attributes = json.loads(msg)['shared']
            # print(fw_attributes)
            if (fw_attributes[self.FW_VERSION_ATTR] == self.current_fw_title and
                fw_attributes[self.FW_TITLE_ATTR] == self.current_fw_version
            ):
                self._report_state(self.UPDATED_ST)
                print("Ya está actualizado")
            elif fw_attributes[self.FW_CHECKSUM_ALG_ATTR].lower() != "sha256":
                print("Algoritmo de hash diastinto a sha256 no soportado")
                self._report_state(self.FAILED_ST)
            else:
                self.hash_recv = fw_attributes[self.FW_CHECKSUM_ATTR]
                print("Starting download of new firmware")
                self._report_state(self.DOWNLOADING_ST)
                self.firmware_length = fw_attributes[self.FW_SIZE_ATTR]
                self.num_chunks = ceil(self.firmware_length/self.chunk_size)
                self.expected_chunk = 0
                mqtt_client.publish(
                    f"v2/fw/request/{self.request_id_firmware}/chunk/0".encode('utf-8'),
                    str(self.chunk_size).encode('utf-8')
                )

        elif topic == fw_chunk_topic:
            print("CHUNK RECIBIDO->>>", topic)
            self.firmware_data += msg
            self.expected_chunk += 1
            if self.expected_chunk < self.num_chunks:
                mqtt_client.publish(
                    f"v2/fw/request/{self.request_id_firmware}/chunk/{self.expected_chunk}".encode('utf-8'),
                    str(self.chunk_size).encode('utf-8')
                )
            else:
                if len(self.firmware_data) == self.firmware_length:
                    print("Firmware recibido correctamente. Tamañano: ", self.firmware_length, "B")
                    hash_calculated = sha256(self.firmware_data).digest().hex()
                    print("hash calculated: ", hash_calculated)
                    print("hash received: ", self.hash_recv)
                    print(self.firmware_data)


    def prepare_for_ota(self):
        """Realiza las suscripciones y publicaciones necesarias para intercambiar
        mensajes en un proceso de OTA posterior. """

        # Suscrito a shared attributes (modificable desde la plataforma, sólo lectura para el cliente)
        # Cuando se solicite la actualización, se actualizan estos atributos:
        # fw_title, fw_version, fw_checksum, fw_checksum_algorithm
        self.mqtt_client.subscribe(b"v1/devices/me/attributes/response/+")
        self.mqtt_client.subscribe(b"v1/devices/me/attributes") # : Esto es más general...

        # Suscripción a topic para recibir los chunks de firmware
        self.mqtt_client.subscribe(b"v2/fw/response/+/chunk/+")

        # Solicitud de atributos relacionados con el firmware
        self.mqtt_client.publish(b"""v1/devices/me/attributes/request/%d""" % self.request_id_attrs,
            b'{"sharedKeys": "%s"}' % updater.REQUIRED_SHARED_KEYS)


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
