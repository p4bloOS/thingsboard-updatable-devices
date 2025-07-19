"""
utils.py
"""

import time
import network
import json
import logging
import os
from ota_helper import UpdatableTBMqttClient, METADATA_FILE_NAME

log = logging.getLogger(__name__)

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
        seconds_count = 0
        while not wlan.isconnected():
            log.debug("Esperando a la conexión wifi...")
            seconds_count = seconds_count + 1
            if seconds_count == 60:
                log.error("Se ha intentado establecer conexión durante 1 minuto sin éxito")
            time.sleep(1)
    log.info(f"Configuración de red establecida: {wlan.ipconfig('addr4')}")


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
        host=thingsboard_config['server_host'],
        port=thingsboard_config['server_port'],
        access_token=thingsboard_config['device_access_token'],
        client_id="micropython_client",
        chunk_size=ota_config['chunk_size'],
        fw_current_title=fw_metadata['title'],
        fw_current_version=fw_metadata['version'],
        fw_filename=ota_config['tmp_filename']
    )


def get_custom_logger(name) -> logging.Logger:

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Si el logger tenía handlers, se eliminan para ser sobrescritos
    if logger.hasHandlers():
        for h in logger.handlers:
            h.close()
        logger.handlers = []

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)

    # Directorio "logs"
    try:
        os.listdir("logs") # Si produce excepxión, el directorio aún no existe
    except OSError:
        os.mkdir("logs")

    # File handler
    file_handler = logging.FileHandler("logs/error.log", mode="a")
    file_handler.setLevel(logging.WARNING)

    # Formatter
    formatter = logging.Formatter("%(levelname)s:%(name)s| %(message)s")
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
