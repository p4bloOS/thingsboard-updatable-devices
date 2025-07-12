"""
utils.py
"""

import time
import network
import json
from machine import reset
from time import sleep
import os
from sdk_utils import verify_checksum

import sys
import lib.umqtt
sys.modules['umqtt']=lib.umqtt

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

# Sufijo para crear el archivo de metadatos asociado al paquete OTA recibido
EXPECTED_METADATA_SUFFIX = ".metadata.json"

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

            expected_fw_metadata = {
                "title": self.firmware_info.get(FW_TITLE_ATTR),
                "version": self.firmware_info.get(FW_VERSION_ATTR)
            }
            with open(self.fw_file_name + EXPECTED_METADATA_SUFFIX, "wb") as firmware_metadata_file:
                firmware_metadata_file.write(json.dumps(expected_fw_metadata))

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


def check_tar_gz_format(ota_file_path):
    """
    Comprueba que un sigue el formato TAR.GZ, lanzando una excepción en caso negativo.
    """
    with open(ota_file_path, 'rb') as ota_file:
        decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
        tar_file = tarfile.TarFile(fileobj=decompressed_file)
        try:
            # Esto dará error si el archivo no sigue el formato tar gz
            tar_file.next()
        except Exception as e :
            raise RuntimeError("No se puede leer el paquete OTA como un archivo en"
               f" formato .tar.gz: {e}")


def read_fw_metadata_json(json_file) -> dict:
    """
    Retorna un diccionario a partir de un archivo JSON.
    Lanza una excepción si el archivo no se puede leer como JSON o si no contiene
    los atributos "title" y "version".
    """
    try:
        fw_metadata = json.loads(json_file.read())
    except ValueError as e:
        raise ValueError(f"Error mientras se cargaba el fichero JSON de metadatos: {e}")
    if ( 'title' not in fw_metadata or 'version' not in fw_metadata):
        raise KeyError("No se han encontrado los atributos esperados en FW_METADATA.json "
            "(\"title\" y \"version\")")
    return fw_metadata


def check_metadata_in_ota_file(ota_file_path):
    """
    Inspecciona como un TAR.GZ un fichero de OTA y comprueba que contenga dentro el
    fichero FW_METADATA.json.
    Los campos "title" y "version" de FW_METADATA.json deberán coincidir con los reportados
    con la plataforma antes del reincio, almacenados un fichero "<ota_file_name>.metadata.json".
    Lanza una excepción si no se superan las comprobaciones.
    """

    metadata_inside_ota_file = None
    with open(ota_file_path, 'rb') as ota_file:
        decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
        tar_file = tarfile.TarFile(fileobj=decompressed_file)
        for file_entry in tar_file:
            if file_entry.name == METADATA_FILE_NAME:
                metadata_file = tar_file.extractfile(file_entry)
                metadata_inside_ota_file = read_fw_metadata_json(metadata_file)
                break
    if metadata_inside_ota_file == None:
        raise ValueError(f"'{METADATA_FILE_NAME} no encontrado en el paquete OTA.'")

    with open(ota_file_path + EXPECTED_METADATA_SUFFIX, 'rb') as expected_metadata_file:
        expected_metadata = read_fw_metadata_json(expected_metadata_file)

    if metadata_inside_ota_file != expected_metadata:
        raise ValueError("Título y versión de firmware del paquete recibido no coinciden con los "
            "reportados por la plataforma")


def delete_ota_package(ota_file_path):
    """
    Elimina el paquete OTA y su fichero de metadatos asociado.
    """
    os.remove(ota_file_path)
    os.remove(ota_file_path + EXPECTED_METADATA_SUFFIX)


def install_ota_package(ota_file_path, ota_config):
    """
    Aplica el paquete OTA sobreescribiendo el sistema de ficheros.
    """

    with open(ota_file_path, 'rb') as ota_file:
        decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
        tar_file = tarfile.TarFile(fileobj=decompressed_file)
        for file_entry in tar_file:
            file_name = file_entry.name
            print(file_name)
            if file_name in ota_config['excluded_files']:
                item_type = 'directorio' if file_name.endswith('/') else 'fichero'
                print(f'Omitiendo {item_type} {file_name}')
                continue
            if file_entry.type == tarfile.DIRTYPE:
                try:
                    os.mkdir(file_entry.name[:-1])
                except OSError as e:
                    if e.errno == 17:
                        print('El directorio ya existe')
                    else:
                        raise e
            else:
                file = tar_file.extractfile(file_entry)
                with open(file_entry.name, "wb") as of:
                    of.write(file.read())


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
