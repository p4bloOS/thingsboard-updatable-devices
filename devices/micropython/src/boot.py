"""
Script de inicio para un dispositivo Micropython genérico.
Establece conexión con la red y, en caso de encontrar un paquete de actualización
OTA, lo intenta instalar, informando a Thingsboard del resultado.
"""

import utils
from gc import collect as gc_collect
from sys import print_exception as sys_print_exception
from thingsboard_ota_helpers.ota_installer import OTAInstaller

def main():

    log = utils.get_custom_logger("boot")
    utils.get_custom_logger("utils")

    # Información inicial
    log.info("Iniciando dispositivo")
    current_fw_metadata = utils.read_firmware_metadata()
    log.info(f"Versión actual de firmware: {current_fw_metadata['title']}({current_fw_metadata['version']})")

    # Se descubre el tipo de conectividad configurada y sus parámetros
    connectivity_config = utils.read_config_file('connectivity.json')
    connection_type = connectivity_config['connection_type']

    # Se establece la conexión Wifi si es necesaria
    if connection_type == "Wifi":
        wifi_params = utils.read_config_file(connectivity_config['config_filename'])
        utils.network_connect(wifi_params)

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
    utils.get_custom_logger("ota_installer")
    ota_installer = OTAInstaller(ota_package_filename, quiet=False)

    # Obtención de un OTAReporter para informar del resultado de la actualización
    ota_reporter = utils.OTAReporter(connection_type)


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
        gc_collect()
        ota_reporter.report_succes(new_fw_title, new_fw_version)

    except Exception as e:
        error_msg = "Excepción producida durante la instalación del paquete de OTA: " + \
            f"({type(e).__name__}) {e}"
        log.error(error_msg)
        sys_print_exception(e)
        ota_reporter.report_failure(error_msg)

    finally:
        ota_reporter.close_connection()
        log.info("Finalizando boot.py")


main()
