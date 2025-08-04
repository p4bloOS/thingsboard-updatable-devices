import asyncio
import gc
import bluetooth
import aioble

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


    async def manage_attributes(self):

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
            self.current_fw_title_char.write("micropython-BLE".encode('utf-8'))
            self.current_fw_version_char.write("v0".encode('utf-8'))
            self.fw_state_char.write("UPDATED".encode('utf-8'))



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
        ota_manager.manage_attributes()
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    asyncio.run(main())
