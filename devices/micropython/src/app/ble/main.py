import asyncio
from gc import mem_free as gc_mem_free, mem_alloc as gc_mem_alloc, collect as gc_collect
from machine import Pin as machine_Pin
import utils

# TO-DO: introducir logging
# Loggers
log = utils.get_custom_logger("main")
utils.get_custom_logger("updatable_ble_peripheral")


async def memory_report(
    period_ms,
    mem_free_char,
    mem_alloc_char
):
    """
    Envía telemetría a la plataforma con datos sobre la memoria del heap
    asignada y libre.
    """
    log.debug("Iniciando envío periódico de telemetría (atributos mem_free, mem_alloc)")
    while True:
        mem_free = gc_mem_free()
        mem_alloc = gc_mem_alloc()
        mem_free_char.write(str(mem_free).encode('utf-8'), send_update=True)
        mem_alloc_char.write(str(mem_alloc).encode('utf-8'), send_update=True)
        await asyncio.sleep_ms(period_ms)


async def listen_gc_collect_rpc( gc_collect_char):
    """
    Insetar coment
    """
    while True:
        await gc_collect_char.written()
        log.info("Garbage Collection invocado desde la plataforma")
        gc_collect()
        gc_collect_char.write("Done".encode('utf-8'))


async def heartbeat_LED():
    """
    Cambio el estado del LED integrado en la ESP32 siguiendo una secuencia periódica,
    para indicar físicamente que el programa principal sigue en marcha.
    """

    led_pin = machine_Pin(2, machine_Pin.OUT)
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
    Inicializa el rol Peripheral de BLE y ejecuta concurrentemente las tareas
    asíncronas definidas.
    """

    updatable_ble_peripheral, (mem_free_char, mem_alloc_char, gc_collect_char) \
    = utils.get_updatable_ble_peripheral()

    await asyncio.gather(
        updatable_ble_peripheral.run_advertising(),
        updatable_ble_peripheral.run_OTA_manager(),
        memory_report(4_000, mem_free_char, mem_alloc_char),
        listen_gc_collect_rpc(gc_collect_char),
        heartbeat_LED()
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    log.info("Iniciando programa principal")
    asyncio.run(main())
