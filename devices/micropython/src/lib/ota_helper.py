"""
ota_helper.py
Inspirado por el proyecto "uota" de mkomon.
(https://github.com/mkomon/uota/tree/daf71b75950ee325168b9c74ec6540df7bf331dd)
"""

import json
import os
import deflate
import tarfile
import sys
import gc
from machine import reset
from time import sleep
from sdk_utils import verify_checksum
import lib.umqtt
sys.modules['umqtt']=lib.umqtt

try:
    import logging
    log = logging.getLogger(__name__)
except ImportError:
    class logging:
        def critical(self, entry):
            print('CRITICAL: ' + entry)
        def error(self, entry):
            print('ERROR: ' + entry)
        def warning(self, entry):
            print('WARNING: ' + entry)
        def info(self, entry):
            print('INFO: ' + entry)
        def debug(self, entry):
            print('DEBUG: ' + entry)
    log = logging()

from tb_device_mqtt import (
    TBDeviceMqttClient,
    ATTRIBUTES_TOPIC,
    FW_VERSION_ATTR,
    FW_TITLE_ATTR,
    FW_STATE_ATTR,
    FW_CHECKSUM_ALG_ATTR, FW_CHECKSUM_ATTR,
    REQUIRED_SHARED_KEYS
)

METADATA_FILE_NAME = "FW_METADATA.json"

# Sufijo para crear el archivo de metadatos asociado al paquete OTA recibido
EXPECTED_METADATA_SUFFIX = ".metadata.json"


class UpdatableTBMqttClient(TBDeviceMqttClient):
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
                firmware_metadata_file.write(json.dumps(expected_fw_metadata))
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
                                    json.dumps({"sharedKeys": REQUIRED_SHARED_KEYS}))
            return


class OTAInstaller():

    def __init__(self, ota_package_path: str, quiet=False):
        self.ota_package_path = ota_package_path
        self.quiet = quiet


    def check_tar_gz_format(self):
        """
        Comprueba que un sigue el formato TAR.GZ, lanzando una excepción en caso negativo.
        """
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
            tar_file = tarfile.TarFile(fileobj=decompressed_file)
            try:
                # Esto dará error si el archivo no sigue el formato tar gz
                tar_file.next()
            except Exception as e :
                raise RuntimeError("No se puede leer el paquete OTA como un archivo en"
                " formato .tar.gz") from e


    @staticmethod
    def __read_fw_metadata_json(json_file) -> dict:
        """
        Retorna un diccionario a partir de un archivo JSON.
        Lanza una excepción si el archivo no se puede leer como JSON o si no contiene
        los atributos "title" y "version".
        """
        try:
            fw_metadata = json.loads(json_file.read())
        except ValueError as e:
            raise ValueError("Error mientras se cargaba el fichero JSON de metadatos") from e
        if ( 'title' not in fw_metadata or 'version' not in fw_metadata):
            raise KeyError("No se han encontrado los atributos esperados en FW_METADATA.json "
                "(\"title\" y \"version\")")
        return fw_metadata


    def check_metadata_in_package(self):
        """
        Inspecciona como un TAR.GZ un fichero de OTA y comprueba que contenga dentro el
        fichero FW_METADATA.json.
        Los campos "title" y "version" de FW_METADATA.json deberán coincidir con los reportados
        con la plataforma antes del reincio, almacenados un fichero "<ota_file_name>.metadata.json".
        Lanza una excepción si no se superan las comprobaciones.
        """

        metadata_inside_ota_file = None
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
            tar_file = tarfile.TarFile(fileobj=decompressed_file)
            for file_entry in tar_file:
                if file_entry.name == METADATA_FILE_NAME:
                    metadata_file = tar_file.extractfile(file_entry)
                    metadata_inside_ota_file = self.__read_fw_metadata_json(metadata_file)
                    break
        if metadata_inside_ota_file == None:
            raise ValueError(f"'{METADATA_FILE_NAME} no encontrado en el paquete OTA.'")

        with open(
            self.ota_package_path + EXPECTED_METADATA_SUFFIX, 'rb'
        ) as expected_metadata_file:
            expected_metadata = self.__read_fw_metadata_json(expected_metadata_file)

        if metadata_inside_ota_file != expected_metadata:
            raise ValueError("Título y versión de firmware del paquete recibido no coinciden con los "
                "reportados por la plataforma")


    def delete_ota_package(self):
        """
        Elimina el paquete OTA y su fichero de metadatos asociado.
        """
        os.remove(self.ota_package_path)
        os.remove(self.ota_package_path + EXPECTED_METADATA_SUFFIX)


    def __recursive_delete(self, path: str, excluded_paths: list):
        """
        Elimina recursivamente todos los ficheros excepto los indicados.
        """

        path = path[:-1] if path.endswith('/') else path
        if path in excluded_paths:
            not self.quiet and log.debug(f"Omitiendo borrado de {path}")
            return

        try:
            children = os.listdir(path)
            # no exception thrown, this is a directory
            for child in children:
                self.__recursive_delete(path + '/' + child, excluded_paths)
        except OSError:
            not self.quiet and log.debug(f"Borrando archivo {path}")
            os.remove(path)
            return

        if path == "" :
            return

        try:
            not self.quiet and log.debug(f"Borrando directorio {path}")
            os.rmdir(path)
        except OSError as e:
            if e.errno == 39:
                not self.quiet and log.debug(f"Directorio {path} no vacío. Hay un archivo excluido dentro")
            else:
                raise e


    def install_firmware(self, excluded_files: list, cleanup: bool):
        """
        Aplica el paquete OTA sobreescribiendo el sistema de ficheros.
        Parámetros:
            ota_file_path: nombre del paquete OTA a aplicar
            ota_config: diccionario
        """
        gc.collect()

        if cleanup:
            excluded_paths = [
                f"/{path[:-1]}"  if path.endswith("/") else f"/{path}" for path in excluded_files
            ] + [
                f"/{self.ota_package_path}",
                f"/{self.ota_package_path}{EXPECTED_METADATA_SUFFIX}"
            ]
            not self.quiet and log.info("Realizando limpieza recursiva")
            self.__recursive_delete("/", excluded_paths)

        not self.quiet and log.info("Aplicando paquete OTA sobre el sistema de ficheros")
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = deflate.DeflateIO(ota_file, deflate.GZIP)
            tar_file = tarfile.TarFile(fileobj=decompressed_file)
            for file_entry in tar_file:
                file_name = file_entry.name
                if file_name in excluded_files:
                    item_type = 'directorio' if file_name.endswith('/') else 'fichero'
                    not self.quiet and log.warning(f'Omitiendo escritura de {item_type} excluido "{file_name}"')
                    continue
                if file_entry.type == tarfile.DIRTYPE:
                    try:
                        not self.quiet and log.debug(f"Creando directorio {file_name}")
                        os.mkdir(file_entry.name[:-1])
                    except OSError as e:
                        if e.errno == 17:
                            log.debug('El directorio ya existe')
                        else:
                            raise e
                else:
                    not self.quiet and log.debug(f"Escribiendo archivo {file_name}")
                    file = tar_file.extractfile(file_entry)
                    with open(file_name, "wb") as of:
                        of.write(file.read())
