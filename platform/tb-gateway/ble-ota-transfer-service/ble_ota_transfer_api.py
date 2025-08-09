from fastapi import FastAPI
from bleak import BleakClient
import httpx

device_name_mac_dict = {}
def device_mac_from_name(name: str) -> str:
    return device_name_mac_dict[name]
TB_REST_API_HOST="host.docker.internal"
TB_REST_API_PORT="8080"

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    import json
    with open('/app/ble-connector-config.json', 'r') as file:
        ble_devices = json.load(file)['devices']
    for dev in ble_devices:
        device_name_mac_dict[dev['name']] = dev['MACAddress']
    print("Devices managed by BLE connector: ", device_name_mac_dict)


@app.post("/trigger_ble_ota_transfer")
async def trigger_ble_ota_transfer(
    device_name: str, fw_title: str, fw_version: str, access_token: str
):
    mac_address = device_mac_from_name(device_name)

    url = f"http://{TB_REST_API_HOST}:{TB_REST_API_PORT}"\
          f"/api/v1/{access_token}/firmware?title={fw_title}&version={fw_version}"
    # url = "http://host.docker.internal:8080/api/v1/ikZwFlLeQxFlerRQd6SJ/firmware?title=micropython-OTA-client&version=v1"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Verifica si la solicitud fue exitosa
    if response.status_code != 200:
        return "No se ha podido recuperar el paquete OTA asociado al dispositivo."

    binary_data = response.content
    print("Respuesta de la API REST de Thingsboard: ", type(binary_data), binary_data)


    return "Paquete OTA transferido"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
