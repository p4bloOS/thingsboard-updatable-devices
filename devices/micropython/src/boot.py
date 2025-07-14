import utils
import sys
import gc
import logging
from time import sleep
from ota_helper import OTAInstaller

def main():

    log = utils.get_custom_logger("boot")
    utils.get_custom_logger("utils")

    # Información inicial
    log.info("Iniciando dispositivo")
    current_fw_metadata = utils.read_firmware_metadata()
    log.info(f"Versión actual de firmware: {current_fw_metadata['title']}({current_fw_metadata['version']})")

    utils.network_connect()

    # Se comprueba si hay un nuevo paquete de actualización disponible. Si no es el caso,
    # se continua con el programa principal
    ota_config = utils.read_config_file('ota_config.json')
    ota_package_filename = ota_config['tmp_filename']
    ota_package_file = None
    try:
        ota_package_file = open(ota_package_filename, 'rb')
        ota_package_file.close()
    except OSError:
        log.info(f"Paquete de actualización OTA ('{ota_package_filename}') no disponible. "
            "Continuando con el programa principal.")
        return

    # Se procede a instalar el paquete de firmware y se reporta el resultado
    utils.get_custom_logger("ota_helper")
    ota_installer = OTAInstaller(ota_package_filename)
    client = utils.get_updatable_thingsboard_client()
    client.connect()
    log.info(f"Instalando nuevo paquete de actualización OTA \"{ota_package_filename}\"")
    try:
        log.debug("Comprobando formato TAR GZ")
        ota_installer.check_tar_gz_format()
        log.debug("Comprobando que los metadatos del paquete coinciden con los esperados")
        ota_installer.check_metadata_in_package()
        log.debug("Instalando firmware sobre el sistema de ficheros")
        ota_installer.install_firmware(
            ota_config['excluded_files'],
            ota_config['clear_filesystem']
        )
        log.debug("Eliminando archivo de actualización aplicado")
        ota_installer.delete_ota_package()
        log.info("El nuevo firmware se ha instalado satisfactoriamente")
        new_fw_metadata = utils.read_firmware_metadata()
        new_fw_title = new_fw_metadata["title"]
        new_fw_version = new_fw_metadata["version"]
        log.info(f"Nueva versión de firmware: {new_fw_title}({new_fw_version})")
        gc.collect()
        client.send_telemetry({
            "current_fw_title": new_fw_title,
            "current_fw_version": new_fw_version,
            "fw_state": "UPDATED"
        })

    except Exception as e:
        error_msg = "Excepción producida durante la instalación del paquete de OTA: " + \
            f"({type(e).__name__}) {e}"
        log.error(error_msg)
        sys.print_exception(e)
        client.send_telemetry( { "fw_state": "FAILED", "fw_error": error_msg } )

    finally:

        log.info("Finalizando boot.py")
        client.disconnect()


main()
