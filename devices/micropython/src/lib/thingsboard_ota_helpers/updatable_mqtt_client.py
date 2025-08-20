import logging
from time import sleep
from machine import reset
from sys import modules as sys_modules
from json import loads as json_loads, dumps as json_dumps
from tb_client_sdk.sdk_utils import verify_checksum
import lib.tb_client_sdk.umqtt
sys_modules['umqtt']=lib.tb_client_sdk.umqtt
import lib.tb_client_sdk.sdk_utils
sys_modules['sdk_utils']=lib.tb_client_sdk.sdk_utils
import lib.tb_client_sdk.provision_client
sys_modules['provision_client']=lib.tb_client_sdk.provision_client
from tb_client_sdk.tb_device_mqtt import (
    TBDeviceMqttClient, ATTRIBUTES_TOPIC, FW_VERSION_ATTR, FW_TITLE_ATTR,
    FW_STATE_ATTR, FW_CHECKSUM_ALG_ATTR, FW_CHECKSUM_ATTR, REQUIRED_SHARED_KEYS
)

log = logging.getLogger("updatable_mqtt_client")
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA


class UpdatableMqttClient(TBDeviceMqttClient):
    """
    Clase derivada de TBDeviceMqttClient con las siguientes características:
    - Constructor con parámetros opcionales adicionales:
        - fw_current_title      (título del firmware actual)
        - fw_current_version    (versión actual del firmware)
        - fw_filename           (nombre de fichero para almacenar el paquete OTA que se reciba)
    - Guardar el firmware recibido en un fichero <fw_filename>, para posibilitar
      la actualización después de reiniciar.
    - Guardar el título y versión notifados del nuevo firmware en un fichero
      <fw_filename>.metadata.json, para poder realizar una comprobación tras el reinicio.
    - No notificar estado UPDATED hasta que el dispositivo aplique la actualización
      después del reinicio.
    """

    def __init__(
        self, host, port=1883, access_token=None, quality_of_service=None, client_id=None, chunk_size=0,
        fw_current_title="Initial",
        fw_current_version="v0",
        fw_filename="new_firmware.tar.gz"
    ):
        super().__init__(
            host, port, access_token, quality_of_service, client_id, chunk_size
        )
        self.current_firmware_info = {
            "current_fw_title" : fw_current_title,
            "current_fw_version" : fw_current_version
        }
        self.fw_file_name = fw_filename


    def _on_decode_message(self, topic, msg):
        super()._on_decode_message(topic, msg)

        if topic.startswith(ATTRIBUTES_TOPIC):
            self.firmware_info = json_loads(msg)

            if '/response/' in topic:
                self.firmware_info = self.firmware_info.get("shared", {}) if isinstance(self.firmware_info, dict) else {}

            if (
                self.firmware_info.get(FW_VERSION_ATTR) is not None and
                self.firmware_info.get(FW_VERSION_ATTR) == self.current_firmware_info.get("current_" + FW_VERSION_ATTR)
            ) and (
                self.firmware_info.get(FW_TITLE_ATTR) is not None and
                self.firmware_info.get(FW_TITLE_ATTR) == self.current_firmware_info.get("current_" + FW_TITLE_ATTR)
            ):
                log.warning("El firmware recibido desde Thingsboard ya está instalado")
                self.current_firmware_info[FW_STATE_ATTR] = "UPDATED"
                self.send_telemetry(self.current_firmware_info)


    def __process_firmware(self):
        self.current_firmware_info[FW_STATE_ATTR] = "DOWNLOADED"
        self.send_telemetry(self.current_firmware_info)
        sleep(1)

        verification_result = verify_checksum(self.firmware_data, self.firmware_info.get(FW_CHECKSUM_ALG_ATTR),
                                                self.firmware_info.get(FW_CHECKSUM_ATTR))

        if verification_result:
            log.info('Checksum verificado')
            self.current_firmware_info[FW_STATE_ATTR] = "VERIFIED"
            self.send_telemetry(self.current_firmware_info)
            sleep(1)

            with open(self.fw_file_name, "wb") as firmware_file:
                firmware_file.write(self.firmware_data)
            log.info(f"El paquete de firmware recibido se ha guardado en {self.fw_file_name}")

            expected_fw_metadata = {
                "title": self.firmware_info.get(FW_TITLE_ATTR),
                "version": self.firmware_info.get(FW_VERSION_ATTR)
            }
            metadata_file_name = self.fw_file_name + EXPECTED_METADATA_SUFFIX
            with open(metadata_file_name, "wb") as firmware_metadata_file:
                firmware_metadata_file.write(json_dumps(expected_fw_metadata))
            log.debug(f"Los metadatos del paquete se han guardado en {metadata_file_name}")

            self.firmware_received = True
            log.info("Reiniciando sistema para instalar nuevo paquete de firmware")
            reset()

        else:
            log.error('Verificación de checksum fallida')
            self.current_firmware_info[FW_STATE_ATTR] = "FAILED"
            self.send_telemetry(self.current_firmware_info)
            self.__request_id = self.__request_id + 1
            self._client.publish("v1/devices/me/attributes/request/{0}".format(self.__request_id),
                                    json_dumps({"sharedKeys": REQUIRED_SHARED_KEYS}))
            return
