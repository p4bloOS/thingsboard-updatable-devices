"""
Biblioteca de utilidades para el proyecto thingsboard-updatable-devices,
desarrollada para Micropython.
"""

from json import load as json_load
import logging

METADATA_FILE_NAME = "FW_METADATA.json"
log = logging.getLogger(__name__)


def read_config_file(file_name: str) -> dict:
    """
    Lee un archivo de configuración en formato JSON ubicado bajo "/config/"
    y devuelve el diccionario equivalente.
    Args:
        file_name (str): nombre del fichero ubicado en /config/
    """
    with open(f'config/{file_name}', 'r') as config_file:
        config = json_load(config_file)
    return config


def read_firmware_metadata() -> dict:
    """
    Lee el sistema y devuelve la información del firmware
    """
    with open(METADATA_FILE_NAME) as fw_file:
        fw_metadata = json_load(fw_file)
    return fw_metadata


def network_connect(network_config):
    """
    Conecta el dispositivo a una red Wi-Fi utilizando la configuración especificada
    en el diccionario network_config (campos "SSID" y "password").
    """
    import network
    from time import sleep
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
            sleep(1)
    log.info(f"Configuración de red establecida: {wlan.ipconfig('addr4')}")


def get_updatable_mqtt_client():
    """
    Crea y devuelve un objeto UpdatableMqttClient con los atributos definidos
    en los ficheros de configuración y metadatos:
    - "/config/thingsboard_config.json": host, port, acces_token.
    - "/config/ota_config.json": chunk_size, fw_filename.
    - "/FW_METADATA.json": fw_current_title, fw_current_version
    """
    from thingsboard_ota_helpers.updatable_mqtt_client import UpdatableMqttClient

    wifi_config = read_config_file("wifi_config.json")
    ota_config = read_config_file("ota_config.json")
    fw_metadata = read_firmware_metadata()

    return UpdatableMqttClient(
        host=wifi_config['server_host'],
        port=wifi_config['server_port'],
        access_token=wifi_config['device_access_token'],
        client_id="micropython_client",
        chunk_size=ota_config['chunk_size'],
        fw_current_title=fw_metadata['title'],
        fw_current_version=fw_metadata['version'],
        fw_filename=ota_config['tmp_filename']
    )


def get_updatable_ble_peripheral():
    """
    TO-DO Insertar coment
    """
    from thingsboard_ota_helpers.updatable_ble_peripheral import UpdatableBLEPeripheral
    import aioble
    from bluetooth import UUID as bluetooth_UUID

    # Creación del UpdatableBLEPeripheral con los argumentos encontrados en la configuración
    ota_config = read_config_file("ota_config.json")
    fw_metadata = read_firmware_metadata()
    updatable_ble_peripheral = UpdatableBLEPeripheral(
        fw_current_title=fw_metadata['title'],
        fw_current_version=fw_metadata['version'],
        fw_filename=ota_config['tmp_filename']
    )

    # Personalización del servicio del Peripheral las características BLE de nuestra aplicación
    # (no han de entrar en conflicto con las dedicadas a la OTA)
    ble_service = updatable_ble_peripheral.ble_service
    MEMFREE_CHARACTERISTIC_UUID          = bluetooth_UUID('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
    MEMALLOC_CHARACTERISTIC_UUID         = bluetooth_UUID('f4c70003-40c5-88cc-c1d6-77bfb6baf772')
    GC_COLLECT_RPC_CHARACTERISTIC_UUID   = bluetooth_UUID('f4c70004-40c5-88cc-c1d6-77bfb6baf772')
    mem_free_char = aioble.Characteristic(ble_service, MEMFREE_CHARACTERISTIC_UUID, read=True, notify=True)
    mem_alloc_char = aioble.Characteristic(ble_service, MEMALLOC_CHARACTERISTIC_UUID, read=True, notify=True)
    gc_collect_char = aioble.Characteristic(ble_service, GC_COLLECT_RPC_CHARACTERISTIC_UUID, write=True)

    updatable_ble_peripheral.register_service() # Se registra el servicio personalizado

    return updatable_ble_peripheral, (mem_free_char, mem_alloc_char, gc_collect_char)



class OTAReporter():

    def __init__(self, type: str):
        self.type = type
        if type == "Wifi":
            get_custom_logger("updatable_mqtt_client")
            self.connection_object = get_updatable_mqtt_client()
            self.connection_object.connect()
        elif type == "BLE":
            get_custom_logger("updatable_ble_peripheral")
            self.connection_object, _ = get_updatable_ble_peripheral()
        elif type == "LoRa":
            get_custom_logger("")
            pass
        else:
            raise ValueError(f"Tipo de conexión no soportada ({type}). Use 'Wifi', 'BLE' o 'LoRa'.")


    def report_failure(self, error_msg: str):

        if self.type == "Wifi":
            self.connection_object.send_telemetry(
                { "fw_state": "FAILED", "fw_error": error_msg }
            )
            log.debug("Estado FAILED reportado a Thingsboard")

        elif self.type == "BLE":
            import asyncio
            async def async_report():
                advertising_task = asyncio.create_task(self.connection_object.run_advertising())
                self.connection_object.fw_state_char.write("FAILED".encode('utf-8'))
                self.connection_object.fw_error_char.write(error_msg.encode('utf-8'))
                log.debug("Estableciendo fw_state a FAILED")
                await asyncio.sleep(10)
                advertising_task.cancel()
                try:
                    await advertising_task
                except Exception:
                    log.debug("Publicitación terminada")
            asyncio.run(async_report())

        elif self.type == "LoRa":
            pass


    def report_succes(self, new_fw_title: str, new_fw_version: str):

        if self.type == "Wifi":
            self.connection_object.send_telemetry({
                "current_fw_title": new_fw_title,
                "current_fw_version": new_fw_version,
                "fw_state": "UPDATED"
            })
            log.debug("Estado UPDATED reportado a Thingsboard")

        elif self.type == "BLE":
            import asyncio
            async def async_report():
                advertising_task = asyncio.create_task(self.connection_object.run_advertising())
                self.connection_object.current_fw_title_char.write   (new_fw_title.encode('utf-8'))
                self.connection_object.current_fw_version_char.write (new_fw_version.encode('utf-8'))
                self.connection_object.fw_state_char.write           ("UPDATED".encode('utf-8'))
                log.debug("Estableciendo fw_state a UPDATED")
                await asyncio.sleep(10)
                advertising_task.cancel()
                try:
                    await advertising_task
                except Exception:
                    log.debug("Publicitación terminada")
            asyncio.run(async_report())

        elif self.type == "LoRa":
            pass

    def close_connection(self):
        if (self.type == "Wifi" or self.type == "BLE"):
            self.connection_object.disconnect()


def get_custom_logger(name) -> logging.Logger:
    """
    Retorna un logger con la configuración preferida para este proyecto.
    En caso de ya existir un logger con el nombre proporcionado, obtiene
    su referencia y lo retorna reconfigurado.
    """
    from os import listdir as os_listdir, mkdir as os_mkdir

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
        os_listdir("logs") # Si produce excepxión, el directorio aún no existe
    except OSError:
        os_mkdir("logs")

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
