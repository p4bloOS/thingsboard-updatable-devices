"""
utils.py
"""

import time
import network
import json
from ota_helper import UpdatableTBMqttClient, METADATA_FILE_NAME


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


def get_updatable_thingsboard_client() -> UpdatableTBMqttClient:
    """
    Crea y devuelve un objeto UpdatableTBMqttClient con los atributos definidos
    en los ficheros de configuración y metadatos:
    - "/config/thingsboard_config.json": host, port, acces_token.
    - "/config/ota_config.json": chunk_size, fw_filename.
    - "/FW_METADATA.json": fw_current_title, fw_current_version
    """

    thingsboard_config = read_config_file("thingsboard_config.json")
    ota_config = read_config_file("ota_config.json")
    fw_metadata = read_firmware_metadata()

    return UpdatableTBMqttClient(
        host=thingsboard_config['server_ip'],
        port=thingsboard_config['server_port'],
        access_token=thingsboard_config['device_access_token'],
        client_id="micropython_client",
        chunk_size=ota_config['chunk_size'],
        fw_current_title=fw_metadata['title'],
        fw_current_version=fw_metadata['version'],
        fw_filename=ota_config['tmp_filename']
    )


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
