Este componente combina un dispositivo que hace gateway empleando el firmware de Theengs OpenMQTTGateway
con un broker MQTT de Eclipse Mosquitto.


Instalación del gateway en la ESP-32:

cd firmware/

esptool erase_flash

esptool --port /dev/ttyACM0 --chip esp32 --baud 921600 --before default_reset --after hard_reset write_flash -z --flash_mode dout --flash_size detect 0xe000 boot_app0.bin 0x1000 ttgo-lora32-v21-bootloader.bin 0x8000 ttgo-lora32-v21-partitions.bin 0x10000 ttgo-lora32-v21-firmware.bin

--baud podría ser tmb 115200
/dev/ttyACM0 depende de tu equipo
