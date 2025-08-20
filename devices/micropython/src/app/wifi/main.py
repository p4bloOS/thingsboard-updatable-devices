"""
Script principal para un dispositivo Micropython genérico.
Es un cliente de la plataforma Thingsboard que permanece a la escucha de
actualizaciones OTA mientras realiza otras tareas.
"""

import asyncio
from gc import mem_free as gc_mem_free, mem_alloc as gc_mem_alloc, collect as gc_collect
from machine import Pin as machine_Pin
from json import dumps as json_dumps
import utils

# Loggers
log = utils.get_custom_logger("main")
utils.get_custom_logger("updatable_mqtt_client")

# Thingsboard MQTT client
client = utils.get_updatable_mqtt_client()


async def memory_report(period_ms):
    """
    Envía telemetría a la plataforma con datos sobre la memoria del heap
    asignada y libre.
    """
    while True:
        mem_free = gc_mem_free()
        mem_alloc = gc_mem_alloc()
        telemetry = {"memory_free" : mem_free, "memory_allocated": mem_alloc}
        client.send_telemetry(telemetry)
        await asyncio.sleep_ms(period_ms)


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
            gc_collect()
            client._client.publish(
                f"v1/devices/me/rpc/response/{request_id}",
                json_dumps({"Garbage collection": "Done"}),
                qos=client.quality_of_service
            )

    client.subscribe_to_all_attributes(on_attributes_change)
    client.set_server_side_rpc_request_handler(on_server_side_rpc_request)

    wifi_config = utils.read_config_file("wifi_config.json")
    check_msg_period_ms = wifi_config['check_msg_period_ms']

    while True:
        client._client.check_msg()
        await asyncio.sleep_ms(check_msg_period_ms)


async def main():
    """
    Ejecuta concurrentemente las tareas asíncronas definidas.
    """
    client.send_attributes({"ota_connectivity" : "Wifi"})
    await asyncio.gather(
        heartbeat_LED(),
        memory_report(1_000),
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
