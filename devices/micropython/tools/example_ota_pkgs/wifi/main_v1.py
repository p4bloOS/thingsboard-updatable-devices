"""
Script principal para un dispositivo Micropython genérico.
Es un cliente de la plataforma Thingsboard que permanece a la escucha de
actualizaciones OTA mientras realiza otras tareas.
"""

import time
import machine
import random
import json
import utils
import asyncio
import gc

# Loggers
log = utils.get_custom_logger("main")
utils.get_custom_logger("ota_helper")

# Thingsboard MQTT client
client = utils.get_updatable_thingsboard_client()


async def memory_and_cpu_report(period_ms):
    """
    Envía telemetría a la plataforma con datos sobre:
    - La memoria del heap asignada y libre.
    - La frecuencia de la CPU.
    """
    while True:
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        cpu_freq = machine.freq()
        telemetry = {
            "memory_free" : mem_free,
            "memory_allocated": mem_alloc,
            "cpu_frequency": cpu_freq
        }
        client.send_telemetry(telemetry)
        await asyncio.sleep_ms(period_ms)


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


async def listen_thingsboard():
    """
    Atiende el comando RPC "garbage_collection" procedente de Thingsboard.
    """

    def on_attributes_change(result, exception):
        if exception is not None:
            log.error(f"Exception: {str(exception)}")
        else:
            log.info(f"Se ha actualizado un atributo: {result}")

    def on_server_side_rpc_request(request_id, request_body):
        if request_body["method"] == "garbage_collection":
            log.info("Garbage Collection invocado desde la plataforma")
            gc.collect()
            client._client.publish(
                f"v1/devices/me/rpc/response/{request_id}",
                json.dumps({"Garbage collection": "Done"}),
                qos=client.quality_of_service
            )

    client.subscribe_to_all_attributes(on_attributes_change)
    client.set_server_side_rpc_request_handler(on_server_side_rpc_request)

    tb_config = utils.read_config_file("thingsboard_config.json")
    check_msg_period_ms = tb_config['check_msg_period_ms']

    while True:
        client._client.check_msg()
        await asyncio.sleep_ms(check_msg_period_ms)


async def main():
    """
    Ejecuta concurrentemente las tareas asíncronas definidas.
    """
    await asyncio.gather(
        heartbeat_LED(),
        memory_and_cpu_report(1_000),
        listen_thingsboard()
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    log.info("Iniciando programa principal")
    client.connect()
    log.info("Conexión establecida con la plataforma Thingsboard")
    asyncio.run(main())
