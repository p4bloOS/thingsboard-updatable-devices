import time
import machine
import random
import json
import utils

# Loggers
log = utils.get_custom_logger("main")
utils.get_custom_logger("ota_helper")

# Thingsboard MQTT client
client = utils.get_updatable_thingsboard_client()


def publish_random_value():
    """
    Envía a la plataforma un dato de telemetría con clave "random_value" y como
    valor un entero aleatorio entre 0 y 8.
    """
    random_value = random.randint(0,8)
    telemetry = {"random_value" : random_value}
    log.debug("Enviando valor random")
    client.send_telemetry(telemetry)
    log.info("Telemetría enviada enviada: %s)" % json.dumps(telemetry))


def on_attributes_change(result, exception):
    if exception is not None:
        log.error(f"Exception: {str(exception)}")
    else:
        log.info(f"Se ha actualizado un atributo: {result}")


if __name__ == "__main__":

    log.info("Iniciando programa principal")
    client.connect()
    log.info("Conexión establecida con la plataforma Thingsboard")

    # client.subscribe_to_all_attributes(on_attributes_change)

    led_pin = machine.Pin(2, machine.Pin.OUT)
    led_pin.off()


    while True:

        # Led signal
        led_pin.on()
        # time.sleep_ms(500)
        led_pin.off()

        client.wait_for_msg()
