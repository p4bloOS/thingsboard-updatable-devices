import utils
import sys

def main():

    print("Iniciando dispositivo...")
    utils.network_connect()

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


    client = utils.get_updatable_thingsboard_client()
    client.connect()

    print(f"Instalando paquete de actualización OTA \"{ota_package_filename}\"")
    try:
        print("check tar gz")
        utils.check_tar_gz_format(ota_package_filename)
        print("check metadata")
        utils.check_metadata_in_ota_file(ota_package_filename)
        print("install ota pkg")
        utils.install_ota_package(ota_package_filename, ota_config)
        print("delete ota pkg")
        utils.delete_ota_package(ota_package_filename)
        new_fw_metadata = utils.read_firmware_metadata()
        client.send_telemetry({
            "current_fw_title": new_fw_metadata["title"],
            "current_fw_version": new_fw_metadata["version"],
            "fw_state": "UPDATED"
        })

    except Exception as e:
        error_msg = "Excepción producida durante la instalación del paquete de OTA: " + \
            f"({type(e).__name__}) {e}"
        print(error_msg)
        sys.print_exception(e)
        client.send_telemetry( { "fw_state": "FAILED", "fw_error": e } )
        return





main()
