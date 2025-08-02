import asyncio
import gc
import bluetooth
import aioble

# UUIDs random para identificar los servicios y características en BLE
# Características que tiene por defecto:
# 00002b29-0000-1000-8000-00805f9b34fb
# 00002a05-0000-1000-8000-00805f9b34fb
# 00002b3a-0000-1000-8000-00805f9b34fb
CUSTOM_SERVICE_UUID = bluetooth.UUID('f4c70001-40c5-88cc-c1d6-77bfb6baf772')
# GENERIC_ATTRIBUTE_SERVICE_UUID = bluetooth.UUID('00001801-0000-1000-8000-00805f9b34fb')
MEMFREE_CHARACTERISTIC_UUID = bluetooth.UUID('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
MEMALLOC_CHARACTERISTIC_UUID = bluetooth.UUID('f4c70003-40c5-88cc-c1d6-77bfb6baf772')
GC_COLLECT_RPC_CHARACTERISTIC_UUID = bluetooth.UUID('f4c70004-40c5-88cc-c1d6-77bfb6baf772')

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
        print("Escuchando RPC...")
        await gc_collect_char.written()
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
                name="Micropython-updatable-thing",
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

    custom_service = aioble.Service(CUSTOM_SERVICE_UUID)
    mem_free_char = aioble.Characteristic(custom_service, MEMFREE_CHARACTERISTIC_UUID, read=True, notify=True)
    mem_alloc_char = aioble.Characteristic(custom_service, MEMALLOC_CHARACTERISTIC_UUID, read=True, notify=True)
    gc_collecto_char = aioble.Characteristic(custom_service, GC_COLLECT_RPC_CHARACTERISTIC_UUID, write=True)

    aioble.register_services(custom_service)

    await asyncio.gather(
        advertise_service(),
        memory_report(1_000, mem_free_char, mem_alloc_char),
        listen_gc_collect_rpc(gc_collecto_char)
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    asyncio.run(main())
