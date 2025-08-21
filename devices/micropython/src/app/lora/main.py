from machine import Pin, SPI
import asyncio
from lora import AsyncSX1276
from json import dumps as json_dumps

# LoRa dedicated pins in Lilygo board
LORA_MOSI = 27
LORA_MISO = 19
LORA_SCLK = 5
LORA_CS = 18
LORA_DIO = 26
LORA_RST = 23

EXTRA_DIO = 35

EUROPE_LORA_FREQ = 868000

# Dependencias
# (lora-sync) no hace falta tal vez
# lora-async
# lora-sx127x


def get_lora_modem():
    lora_cfg = { 'freq_khz': EUROPE_LORA_FREQ,
        "sf": 8,
        "bw": "500",  # kHz
        "coding_rate": 8,
        "preamble_len": 12,
        "output_power": 14,
    }

    spi = SPI(
        1, baudrate=2000_000, polarity=0, phase=0,
        miso=Pin(LORA_MISO), mosi=Pin(LORA_MOSI), sck=Pin(LORA_SCLK)
    )
    cs = Pin(LORA_CS)

    return AsyncSX1276(spi, cs,
                    dio0=Pin(LORA_DIO),  # Optional, recommended
                    dio1=Pin(EXTRA_DIO),
                    reset=Pin(LORA_RST),  # Optional, recommended
                    lora_cfg=lora_cfg)


async def recv_coro(modem):
    while True:
        print("Receiving...")
        rx = await modem.recv(2000)
        if rx:
            print(f"Received: {rx!r}")
        else:
            print("Receive timeout!")

async def send_coro(modem):
    counter = 0
    while True:
        print("Sending...")
        msg = json_dumps({
            #"model": "ESP32TEMP",
            "id": "AA:BB:CC:DD:EE:FF",
            #"tempc": "57"
            "count": str(counter)
        }).encode("utf-8")
        print("mensaje a enviar: ", msg)
        await modem.send(msg)
        print("Sent!")
        await asyncio.sleep(5)
        counter += 1


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


async def main():
    """
    Ejecuta concurrentemente las tareas asíncronas definidas.
    """
    lora_modem = get_lora_modem()
    await asyncio.gather(
        heartbeat_LED(),
        recv_coro(lora_modem),
        send_coro(lora_modem)
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    asyncio.run(main())
