from fastapi import FastAPI
from bleak import BleakClient
import paho.mqtt.client as mqtt
import json
import httpx
import base64
import binascii

TB_REST_API_HOST="host.docker.internal"
TB_REST_API_PORT="8080"

# BLE
FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID = 'f4c7000e-40c5-88cc-c1d6-77bfb6baf772'
BLE_FRAGMENT_SIZE = 128

# LoRa
MOSQUITTO_BROKER_HOST = "host.docker.internal"
MOSQUITTO_BROKER_PORT = 1884
MQTT_USERNAME = "device"
MQTT_PASSWORD = "updatable"
LORA_FRAGMENT_SIZE = 128

app = FastAPI()

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def device_mac_from_name(name: str) -> str:
    with open('/tb-gw-config/myBleConnector.json', 'r') as file:
        ble_devices = json.load(file)['devices']
    device_name_mac_dict = {}
    for dev in ble_devices:
        device_name_mac_dict[dev['name']] = dev['MACAddress']
    print("Dispositivos manejados por el connector BLE: ", device_name_mac_dict)
    return device_name_mac_dict[name]


async def transfer_firmware_BLE(mac_address, fw_data):
    import traceback
    try:
        async with BleakClient(mac_address) as client:
            fw_size = len(fw_data)
            print(f"Tamaño del firmware: {fw_size} bytes")
            coded_fw_size = fw_size.to_bytes(4, byteorder='big')
            await client.write_gatt_char(FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID, coded_fw_size, response=True)
            for i in range(0, fw_size, BLE_FRAGMENT_SIZE):
                fragment = fw_data[i : i+BLE_FRAGMENT_SIZE]
                print(f"Escribiendo fragmento {i}")
                await client.write_gatt_char(FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID, fragment, response=True)
    except Exception as e:
            print(f"Ocurrió un error: {e}")
            traceback.print_exc()


@app.post("/trigger_ble_ota_transfer")
async def trigger_ble_ota_transfer(
    device_name: str, fw_title: str, fw_version: str, access_token: str
):
    print(f"Se transferirá el paquete OTA al dispositivo {device_name}")
    mac_address = device_mac_from_name(device_name)

    url = f"http://{TB_REST_API_HOST}:{TB_REST_API_PORT}"\
          f"/api/v1/{access_token}/firmware?title={fw_title}&version={fw_version}"
    print(f"Recuperando paquete OTA mediante la API REST del servidor Thingsboard (GET {url})")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Verifica si la solicitud fue exitosa
    if response.status_code != 200:
        print("Solicitud fallida")
        return "No se ha podido recuperar el paquete OTA asociado al dispositivo."

    binary_data = response.content
    print("Firmware recibido.")

    print("Iniciando transferencia del firmware")
    await transfer_firmware_BLE(mac_address, binary_data)

    return "Paquete OTA transferido"


async def transfer_firmware_LoRa(lora_id, fw_data):

    mqttc.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqttc.connect(MOSQUITTO_BROKER_HOST, MOSQUITTO_BROKER_PORT)
    mqttc.loop_start()

    fw_fragments_topic = f"thingsboard/OMG_ESP32_LORA/commands/MQTTtoLORA/reliable/{lora_id}"

    fw_size = len(fw_data)
    print(f"Tamaño del firmware: {fw_size} bytes")
    # coded_fw_size = fw_size.to_bytes(4, byteorder='big')
    for i in range(0, fw_size, LORA_FRAGMENT_SIZE):
        print(f"Enviando fragmento {i}")
        fragment = fw_data[i : i+LORA_FRAGMENT_SIZE]
        fragment_str = base64.b64encode(fragment).decode('utf-8')
        msg_to_send = json.dumps({
            "fw_fragment": fragment_str
        }).encode('utf-8')
        msg_info = mqttc.publish(fw_fragments_topic, msg_to_send, qos=2)
        msg_info.wait_for_publish()

    mqttc.disconnect()
    mqttc.loop_stop()




@app.post("/trigger_lora_ota_transfer")
async def trigger_lora_ota_transfer(
    device_name: str, fw_title: str, fw_version: str, access_token: str, lora_id: str
):
    print(f"Se transferirá el paquete OTA al dispositivo {lora_id}")

    url = f"http://{TB_REST_API_HOST}:{TB_REST_API_PORT}"\
          f"/api/v1/{access_token}/firmware?title={fw_title}&version={fw_version}"
    print(f"Recuperando paquete OTA mediante la API REST del servidor Thingsboard (GET {url})")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Verifica si la solicitud fue exitosa
    if response.status_code != 200:
        print("Solicitud fallida")
        return "No se ha podido recuperar el paquete OTA asociado al dispositivo."

    binary_data = response.content
    print("Firmware recibido.")

    print("Iniciando transferencia del firmware")
    await transfer_firmware_LoRa(lora_id, binary_data)

    return "Implementando para LoRa"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
