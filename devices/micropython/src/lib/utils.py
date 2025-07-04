"""
utils.py
"""

import time
import network
import json
from machine import reset
from time import sleep
from sdk_utils import verify_checksum
from tb_device_mqtt import (
    TBDeviceMqttClient,
    ATTRIBUTES_TOPIC,
    FW_VERSION_ATTR,
    FW_TITLE_ATTR,
    FW_STATE_ATTR,
    FW_CHECKSUM_ALG_ATTR, FW_CHECKSUM_ATTR,
    REQUIRED_SHARED_KEYS
)

import deflate
import tarfile

METADATA_FILE_NAME = "FW_METADATA.json"

def read_config_file(file_name: str) -> dict:
    """
    Lee un archivo de configuración en formato JSON ubicado bajo "/config/"
    y devuelve el diccionario equivalente.
    Args:
        file_name (str): nombre del fichero ubicado en /config/
    """
    with open(f'config/{file_name}', 'r') as config_file:
        config = json.load(config_file)
    return config


def read_firmware_metadata() -> dict:
    """
    Lee el sistema y devuelve la información del firmware
    """
    with open(METADATA_FILE_NAME) as fw_file:
        fw_metadata = json.load(fw_file)
    return fw_metadata


def network_connect():
    """
    Conecta el dispositivo a una red Wi-Fi utilizando la configuración definida
    en /config/network_config.json ("SSID" y "password").
    """
    network_config = read_config_file("network_config.json")
    wlan = network.WLAN(network.WLAN.IF_STA)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(network_config['SSID'], network_config['password'])
        while not wlan.isconnected():
            print("Esperando a la conexión wifi...")
            time.sleep(1)
    print('Configuración de red establecida:', wlan.ipconfig('addr4'))


# OTA update utils:

class UpdatableTBMqttClient(TBDeviceMqttClient):

    fw_file_name = "new_firmware.tar.gz"

    # Reporta que el firmware notificado desde Thingsboard ya está instalado
    # (estado UPDATED)
    def _on_decode_message(self, topic, msg):
        super()._on_decode_message(topic, msg)

        if topic.startswith(ATTRIBUTES_TOPIC):
            self.firmware_info = json.loads(msg)

            if '/response/' in topic:
                self.firmware_info = self.firmware_info.get("shared", {}) if isinstance(self.firmware_info, dict) else {}

            if (
                self.firmware_info.get(FW_VERSION_ATTR) is not None and
                self.firmware_info.get(FW_VERSION_ATTR) == self.current_firmware_info.get("current_" + FW_VERSION_ATTR)
            ) and (
                self.firmware_info.get(FW_TITLE_ATTR) is not None and
                self.firmware_info.get(FW_TITLE_ATTR) == self.current_firmware_info.get("current_" + FW_TITLE_ATTR)
            ):
                print('Firmware is the same')
                self.current_firmware_info[FW_STATE_ATTR] = "UPDATED"
                self.send_telemetry(self.current_firmware_info)


    # Guarda el firmware recibido en el fichero con el nombre apropiado (no
    # notifica UPDATED hasta que el dispositivo realice la actualización
    # después del reinicio)
    def __process_firmware(self):
        self.current_firmware_info[FW_STATE_ATTR] = "DOWNLOADED"
        self.send_telemetry(self.current_firmware_info)
        sleep(1)

        verification_result = verify_checksum(self.firmware_data, self.firmware_info.get(FW_CHECKSUM_ALG_ATTR),
                                                self.firmware_info.get(FW_CHECKSUM_ATTR))

        if verification_result:
            print('Checksum verified!')
            self.current_firmware_info[FW_STATE_ATTR] = "VERIFIED"
            self.send_telemetry(self.current_firmware_info)
            sleep(1)

            with open(self.fw_file_name, "wb") as firmware_file:
                firmware_file.write(self.firmware_data)

            self.firmware_received = True
            reset()
        else:
            print('Checksum verification failed!')
            self.current_firmware_info[FW_STATE_ATTR] = "FAILED"
            self.send_telemetry(self.current_firmware_info)
            self.__request_id = self.__request_id + 1
            self._client.publish("v1/devices/me/attributes/request/{0}".format(self.__request_id),
                                    json.dumps({"sharedKeys": REQUIRED_SHARED_KEYS}))
            return


def get_updatable_thingsboard_client() -> UpdatableTBMqttClient:
    """
    Crea y devuelve un objeto TBDeviceMqttClient con los atributos definidos
    en los ficheros de configuración:
    - "/config/thingsboard_config.json": host, port y acces_token.
    - "/config/ota_config.json": chunk_size.
    - * Metadata establece title y version
    - * ota_config.json establece el filename
    """
    thingsboard_config = read_config_file("thingsboard_config.json")
    ota_config = read_config_file("ota_config.json")
    fw_metada = read_firmware_metadata()

    client = UpdatableTBMqttClient(
        host=thingsboard_config['server_ip'],
        port=thingsboard_config['server_port'],
        access_token=thingsboard_config['device_access_token'],
        client_id="micropython_client",
        chunk_size=ota_config['chunk_size']
    )
    client.current_firmware_info = {
        "current_fw_title" : fw_metada["title"],
        "current_fw_version" : fw_metada["version"]
    }
    client.fw_file_name = ota_config["tmp_filename"]

    return client


def install_ota_package(ota_file, ota_config):

    decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
    files = tarfile.TarFile(fileobj=decompressed_file)

    # Verificar que sea un tar.gz de verdad
    #
    #
    # Leer archivos del paquete (FW_METADATA.json):
    metadata_found = False
    for f in files:
        if f.name == METADATA_FILE_NAME:
            metadata_found = True

            break
    if metadata_found == False:
        raise RuntimeError(f"'{METADATA_FILE_NAME} not found in OTA package'")



    #
    #   El FW_METADATA.json del paquete debe coincidir con el title y version
    #   reportadas por Thingsboard (deben guardarse en otro archivo antes de reinciar...,
    #   un archivo tipo new_firmware.tar.gz.thingsboard_info)
    #
    # Leer configuración de OTA
    # Aplicar OTA
    # Cambiar FW_METADATA.json
    # Borrar paquete



    return


def wait_until(t):
    """
    Realiza un sleep hasta un instante de referencia en milisegundos "t".
    Ejemplo:
        current_time = time.ticks_ms()
        next_time = time.ticks_add(current_time, 1000)
        ... Hacer algún proceso ...
        wait_until(next_time)
    """
    wait_time = time.ticks_diff(t, time.ticks_ms())
    if wait_time > 0:
        time.sleep_ms(wait_time)
