import utils

print("Iniciando dispositivo...")

ota_config = utils.read_config_file('ota_config.json')
ota_package_filename = ota_config['tmp_filename']
try:
    ota_package_file = open(ota_package_filename, 'rb')
except OSError as e:
    print(f"Paquete de actualización OTA ('{ota_package_filename}') no disponible: '{e}'"
        "Continuando con el programa programa principal.")
    exit(0)

try:
    print(f"Instalando paquete de actualización OTA \"'{ota_package_filename}'\"")
    utils.install_ota_package(ota_package_file)

except Exception as e:
    print(f"Error al instalar el paquete de OTA. Razón: '{e}'")



# Aquí en este archivo se comprueba que el archivo de OTA esté y se aplica.
#ota_config["tmp_filename"]

print("AQUÍ EL BOOT.PY")
