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


async def memory_report(period_ms):
    """
    Envía telemetría a la plataforma conn datos sobre la memoria del heap
    asignada y libre.
    """
    while True:
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        telemetry = {"memory_free" : mem_free, "memory_allocated": mem_alloc}
        client.send_telemetry(telemetry)
        await asyncio.sleep_ms(period_ms)


async def heartbeat_LED():

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


async def listen_thingsboard(period_ms):

    def on_attributes_change(result, exception):
        if exception is not None:
            log.error(f"Exception: {str(exception)}")
        else:
            log.info(f"Se ha actualizado un atributo: {result}")

    def on_server_side_rpc_request(request_id, request_body):
        print(request_id, request_body)
        if request_body["method"] == "garbage_collection":
            gc.collect()
            client._client.publish(
                f"v1/devices/me/rpc/response/{request_id}",
                json.dumps({"Garbage collection": "Done"}),
                qos=client.quality_of_service
            )

    client.subscribe_to_all_attributes(on_attributes_change)
    client.set_server_side_rpc_request_handler(on_server_side_rpc_request)

    while True:
        client._client.check_msg()
        await asyncio.sleep_ms(period_ms)


async def main():
    await asyncio.gather(
        heartbeat_LED(),
        memory_report(1_000),
        listen_thingsboard(1_000)
    )


if __name__ == "__main__":
    log.info("Iniciando programa principal")
    client.connect()
    log.info("Conexión establecida con la plataforma Thingsboard")
    asyncio.run(main())
