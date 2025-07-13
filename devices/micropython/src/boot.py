import utils
import sys
from ota_helper import OTAInstaller

def main():

    # Información inicial
    print("Iniciando dispositivo...")
    current_fw_metadata = utils.read_firmware_metadata()
    print(f"Versión actual de firmware: {current_fw_metadata['title']}({current_fw_metadata['version']})")

    utils.network_connect() # conexión a la red

    # Se comprueba si hay un nuevo paquete de actualización disponible. Si no es el caso,
    # se continua con el programa principal
    ota_config = utils.read_config_file('ota_config.json')
    ota_package_filename = ota_config['tmp_filename']
    ota_package_file = None
    try:
        ota_package_file = open(ota_package_filename, 'rb')
        ota_package_file.close()
    except OSError as e:
        print(f"Paquete de actualización OTA ('{ota_package_filename}') no disponible: {e}")
        print("Continuando con el programa principal.")
        return

    # Se procede a instalar el paquete de firmware y se reporta el resultado
    ota_installer = OTAInstaller(ota_package_filename)
    client = utils.get_updatable_thingsboard_client()
    client.connect()
    print(f"Instalando paquete de actualización OTA \"{ota_package_filename}\"")
    try:
        print("Comprobando formato TAR GZ")
        ota_installer.check_tar_gz_format()
        print("Comprobando que los datos del paquete coinciden con los esperados")
        ota_installer.check_metadata_in_package()
        print("Instalando firmware sobre el sistema de ficheros")
        ota_installer.install_firmware(
            ota_config['excluded_files'],
            ota_config['clear_filesystem']
        )
        print("Eliminando paquete de actualización aplicado")
        ota_installer.delete_ota_package()
        print("El nuevo firmware se ha instalado satisfactoriamente")
        new_fw_metadata = utils.read_firmware_metadata()
        new_fw_title = new_fw_metadata["title"]
        new_fw_version = new_fw_metadata["version"]
        print(f"Nueva versión de firmware: {new_fw_title}({new_fw_version})")
        client.send_telemetry({
            "current_fw_title": new_fw_title,
            "current_fw_version": new_fw_version,
            "fw_state": "UPDATED"
        })

    except Exception as e:
        error_msg = "Excepción producida durante la instalación del paquete de OTA: " + \
            f"({type(e).__name__}) {e}"
        print(error_msg)
        sys.print_exception(e)
        client.send_telemetry( { "fw_state": "FAILED", "fw_error": e } )


main()
