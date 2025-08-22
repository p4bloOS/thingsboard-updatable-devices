import asyncio
from machine import Pin
from json import dumps as json_dumps
from gc import mem_free as gc_mem_free, mem_alloc as gc_mem_alloc, collect as gc_collect
import utils

# Loggers
log = utils.get_custom_logger("main")
utils.get_custom_logger("updatable_lora_node")


async def memory_report(lora_node, period_s):
    log.debug("Iniciando envío periódico de telemetría (atributos mem_free, mem_alloc) "
       f"cada {period_s} segundos.")
    while True:
        mem_free = gc_mem_free()
        mem_alloc = gc_mem_alloc()
        telemetry = {"memory_free" : mem_free, "memory_allocated": mem_alloc}
        await lora_node.send("telemetry", telemetry)
        await asyncio.sleep(period_s)


async def heartbeat_LED():
    """
    Cambio el estado del LED integrado en la ESP32 siguiendo una secuencia periódica,
    para indicar físicamente que el programa principal sigue en marcha.
    """
    led_pin = Pin(25, Pin.OUT)
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


def on_message_callback(recv_data):
    if recv_data.get("rpc") == "garbage_collection":
        log.info("Garbage Collection invocado desde la plataforma")
        gc_collect()


async def main():
    """
    Ejecuta concurrentemente las tareas asíncronas definidas.
    """
    lora_node = utils.get_updatable_lora_node()
    lora_node.connect()
    lora_node.set_callback(on_message_callback)
    await asyncio.gather(
        heartbeat_LED(),
        lora_node.listen(),
        memory_report(lora_node, 2),
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    log.info("Iniciando programa principal")
    asyncio.run(main())
