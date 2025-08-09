import asyncio
import gc
import machine
import bluetooth
import aioble

from hashlib import sha256

def verify_checksum(firmware_data, checksum_alg, checksum):
    if firmware_data is None:
        print('Firmware was not received!')
        return False
    if checksum is None:
        print('Checksum was\'t provided!')
        return False
    checksum_of_received_firmware = None
    print('Checksum algorithm is: %s' % checksum_alg)
    if checksum_alg.lower() == "sha256":
        checksum_of_received_firmware = "".join(["%.2x" % i for i in sha256(firmware_data).digest()])
    else:
        print('Client error. Unsupported checksum algorithm.')

    print(checksum_of_received_firmware)

    return checksum_of_received_firmware == checksum


# UUIDs random para identificar los servicios y características en BLE
# Características que tiene por defecto:
# 00002b29-0000-1000-8000-00805f9b34fb
# 00002a05-0000-1000-8000-00805f9b34fb
# 00002b3a-0000-1000-8000-00805f9b34fb
# # GENERIC_ATTRIBUTE_SERVICE_UUID = bluetooth.UUID('00001801-0000-1000-8000-00805f9b34fb')

DEVICE_NAME = "Micropython-updatable-thing"
CUSTOM_SERVICE_UUID                  = bluetooth.UUID('f4c70001-40c5-88cc-c1d6-77bfb6baf772')

# Características BLE para la aplicación
MEMFREE_CHARACTERISTIC_UUID          = bluetooth.UUID('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
MEMALLOC_CHARACTERISTIC_UUID         = bluetooth.UUID('f4c70003-40c5-88cc-c1d6-77bfb6baf772')
GC_COLLECT_RPC_CHARACTERISTIC_UUID   = bluetooth.UUID('f4c70004-40c5-88cc-c1d6-77bfb6baf772')


class BleThingsboardOtaManager:

    # Características BLE para la actualización OTA (atributos compartidos)
    FW_TITLE_CHARACTERISTIC_UUID         = bluetooth.UUID('f4c70005-40c5-88cc-c1d6-77bfb6baf772')
    FW_VERSION_CHARACTERISTIC_UUID       = bluetooth.UUID('f4c70006-40c5-88cc-c1d6-77bfb6baf772')
    FW_SIZE_CHARACTERISTIC_UUID          = bluetooth.UUID('f4c70007-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_CHARACTERISTIC_UUID      = bluetooth.UUID('f4c70008-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_ALG_CHARACTERISTIC_UUID  = bluetooth.UUID('f4c70009-40c5-88cc-c1d6-77bfb6baf772')

    # Características BLE para la actualización OTA (telemetría)
    CURRENT_FW_TITLE_CHARACTERISTIC_UUID    = bluetooth.UUID('f4c7000a-40c5-88cc-c1d6-77bfb6baf772')
    CURRENT_FW_VERSION_CHARACTERISTIC_UUID  = bluetooth.UUID('f4c7000b-40c5-88cc-c1d6-77bfb6baf772')
    FW_STATE_CHARACTERISTIC_UUID            = bluetooth.UUID('f4c7000c-40c5-88cc-c1d6-77bfb6baf772')

    # Característica para distinguir el tipo de OTA
    OTA_CONNECTIVITY_CHARACTERISTIC_UUID    = bluetooth.UUID('f4c7000d-40c5-88cc-c1d6-77bfb6baf772')

    # Característica sobre la cual recibir el firmware por fragmentos
    FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID = bluetooth.UUID('f4c7000e-40c5-88cc-c1d6-77bfb6baf772')


    def __init__(self, ble_service: aioble.Service):

        # Telemtría sobre el estado de la OTA
        self.current_fw_title_char = aioble.Characteristic(ble_service, self.CURRENT_FW_TITLE_CHARACTERISTIC_UUID, read=True)
        self.current_fw_version_char = aioble.Characteristic(ble_service, self.CURRENT_FW_VERSION_CHARACTERISTIC_UUID, read=True)
        self.fw_state_char = aioble.Characteristic(ble_service, self.FW_STATE_CHARACTERISTIC_UUID, read=True)

        # Atributos compartidos para la actuaización OTA
        self.fw_title_char = aioble.BufferedCharacteristic(ble_service, self.FW_TITLE_CHARACTERISTIC_UUID, write=True, capture=True, max_len=64)
        self.fw_version_char = aioble.Characteristic(ble_service, self.FW_VERSION_CHARACTERISTIC_UUID, write=True, capture=True)
        self.fw_size_char = aioble.Characteristic(ble_service, self.FW_SIZE_CHARACTERISTIC_UUID, write=True,capture=True)
        self.fw_checksum_char = aioble.Characteristic(ble_service, self.FW_CHECKSUM_CHARACTERISTIC_UUID, write=True, capture=True)
        self.fw_checksum_alg_char = aioble.Characteristic(ble_service, self.FW_CHECKSUM_ALG_CHARACTERISTIC_UUID, write=True, capture=True)

        # Atributo "ota_connectivity" para que la Rule Chain distinga el tipo de OTA
        self.ota_connectivity_char = aioble.Characteristic(ble_service, self.OTA_CONNECTIVITY_CHARACTERISTIC_UUID, read=True)

        # Característica sobre la cual recibir el firmware por fragmentos
        self.firmware_fragment_char = aioble.BufferedCharacteristic(ble_service, self.FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID, write=True, capture=True, max_len=128)


    async def manage_attributes(self):

        self.ota_connectivity_char.write("BLE".encode('utf-8'))


        _, coded_fw_size = await self.firmware_fragment_char.written()
        fw_size = int.from_bytes(coded_fw_size, 'big')
        expected_checksum = "76ca55952f85f0fc5270f46cf1322e9a7d40dfb1780ca71c98e95a8d991cd271"
        print(type(fw_size), " recibido: ", fw_size)
        fw_data = bytearray()
        size_received = 0
        while size_received < fw_size:
            _, fw_fragment = await self.firmware_fragment_char.written()
            # print(type(fw_fragment), " recibido: ", fw_fragment)
            fw_data.extend(fw_fragment)
            size_received = size_received + len(fw_fragment)
        print("Recibidos todos los datos!")
        if verify_checksum(fw_data, "sha256", expected_checksum):
            print("ESTÁ BIEN")
        else:
            print("NO ESTÁ BIEN")
        return

        while True:
            # Esperar al estado INITIATED en Thingsboard
            _ , data = await self.fw_title_char.written()
            print("fw_title: ", data )
            _ , data = await self.fw_version_char.written()
            print("fw_version: ", data )
            _ , data = await self.fw_size_char.written()
            print("fw_size: ", data )
            _ , data = await self.fw_checksum_char.written()
            print("fw_checksum: ", data )
            _ , data = await self.fw_checksum_alg_char.written()
            print("fw_checksum_alg: ", data )

            # Reportar el estado a Thingsboard
            self.current_fw_title_char.write("micropython-OTA-client".encode('utf-8'))
            self.current_fw_version_char.write("v1".encode('utf-8'))
            self.fw_state_char.write("DOWNLOADING".encode('utf-8'))
            await asyncio.sleep_ms(30000)
            self.fw_state_char.write("FAILED".encode('utf-8'))



async def memory_report(
    period_ms,
    mem_free_char: aioble.Characteristic,
    mem_alloc_char: aioble.Characteristic
):
    """
    Envía telemetría a la plataforma con datos sobre la memoria del heap
    asignada y libre.
    """
    while True:
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        mem_free_char.write(str(mem_free).encode('utf-8'), send_update=True)
        mem_alloc_char.write(str(mem_alloc).encode('utf-8'), send_update=True)
        # print("mem_free: ", mem_free, "; mem_alloc: ", mem_alloc)
        await asyncio.sleep_ms(period_ms)


async def listen_gc_collect_rpc( gc_collect_char: aioble.Characteristic ):
    """
    Insetar coment
    """
    while True:
        await gc_collect_char.written()
        print("RPC recibido")
        gc.collect()
        gc_collect_char.write("Done".encode('utf-8'))



async def advertise_service():
    """
    Insertar coment
    """
    ADV_INTERVAL_US = const(250000)
    GENERIC_DEVICE_APPEARANCE = const(0)
    while True:
        connection = await aioble.advertise(
                ADV_INTERVAL_US,
                name=DEVICE_NAME,
                services=[CUSTOM_SERVICE_UUID],
                appearance=GENERIC_DEVICE_APPEARANCE,
                manufacturer=(0xabcd, b"1234"),
            )
        print("Connection from", connection.device)


async def heartbeat_LED():
    """
    Cambio el estado del LED integrado en la ESP32 siguiendo una secuencia periódica,
    para indicar físicamente que el programa principal sigue en marcha.
    """

    led_pin = machine.Pin(2, machine.Pin.OUT)
    led_pin.off()
    while True:
        led_pin.on()
        await asyncio.sleep_ms(1700)
        led_pin.off()
        await asyncio.sleep_ms(100)
        led_pin.on()
        await asyncio.sleep_ms(100)
        led_pin.off()
        await asyncio.sleep_ms(100)




async def main():
    """
    Inicializa el rol Peropheral de BLE y ejecuta concurrentemente las tareas
    asíncronas definidas.
    """
    addr = aioble.config("mac")
    print("Dirección MAC de BLE: ", addr[1])

    # aioble.config(mtu=64)

    custom_service = aioble.Service(CUSTOM_SERVICE_UUID)

    mem_free_char = aioble.Characteristic(custom_service, MEMFREE_CHARACTERISTIC_UUID, read=True, notify=True)
    mem_alloc_char = aioble.Characteristic(custom_service, MEMALLOC_CHARACTERISTIC_UUID, read=True, notify=True)
    gc_collect_char = aioble.Characteristic(custom_service, GC_COLLECT_RPC_CHARACTERISTIC_UUID, write=True)

    ota_manager = BleThingsboardOtaManager(custom_service)

    aioble.register_services(custom_service)

    await asyncio.gather(
        advertise_service(),
        memory_report(1_000, mem_free_char, mem_alloc_char),
        listen_gc_collect_rpc(gc_collect_char),
        heartbeat_LED(),
        ota_manager.manage_attributes()
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    asyncio.run(main())
