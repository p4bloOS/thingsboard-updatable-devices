import logging
from hashlib import sha256
from machine import reset
from gc import collect as gc_collect
from json import dumps as json_dumps, loads as json_loads
from network import WLAN, STA_IF
from ubinascii import hexlify

log = logging.getLogger("updatable_lora_node")
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA


class UpdatableLoraNode():

    def __init__(self,
        lora_modem,
        fw_current_title="Initial",
        fw_current_version="v0",
        fw_filename="new_firmware.tar.gz",
    ):
        self.fw_current_title = fw_current_title
        self.fw_current_version = fw_current_version
        self.fw_filename = fw_filename
        self.device_id = self._get_mac_address()
        self.lora_modem = lora_modem
        lora_modem_info = str(self.lora_modem.__dict__)
        log.info(f"Modem lora = {lora_modem_info}")
        self.callback = None


    def _get_mac_address(self):
        wlan = WLAN(STA_IF)
        raw_mac = wlan.config('mac')
        mac = hexlify(raw_mac).decode()
        print(f"MAC Address: {mac}")
        return mac


    def _verify_checksum(self, firmware_data, checksum_alg, checksum):
        checksum_of_received_firmware = None
        if checksum_alg.lower() == "sha256":
            checksum_of_received_firmware = "".join(["%.2x" % i for i in sha256(firmware_data).digest()])
        else:
            log.error("Algoritmo de checksum no soportado (solo SHA256)")
        log.debug(f"Checksum del firmware recibido: {checksum_of_received_firmware}")
        return checksum_of_received_firmware == checksum



    async def connect(self):
        import asyncio
        self.lora_modem.calibrate() # Calibración inicial para oscilador RC, PLL y ADC
        await self.send("connect", {})
        await asyncio.sleep(2)
        connectivity_attrs = {"ota_connectivity": "LoRa", "lora_id": self.device_id}
        await self.send("attributes", connectivity_attrs)


    async def send(self, subtopic, msg):
        msg_bytes = json_dumps({
            "id": f"{self.device_id}/{subtopic}",
            "msg": msg
        }).encode("utf-8")
        await self.lora_modem.send(msg_bytes)


    def set_callback(self, callback):
        """
        Establece la función de callback que se llamará más tarde.

        :param callback: Función que se usará como callback.
        """
        self.callback = callback
        log.debug("Callback de recepción de mensajes establecido.")


    async def listen(self):
        log.info("A la escucha de mensajes LoRa")
        while True:
            rx = await self.lora_modem.recv()
            log.debug(f'Paquete recibido ({len(rx)} bytes, SNR={rx.snr}, RSSI={rx.rssi}, '
                f'valid_CRC={rx.valid_crc}). Contenido: {rx}')
            try:
                recv_data = json_loads(rx)
                recv_data["id"]
            except ValueError as e:
                log.debug("El mensaje recibido no está en formato JSON")
                continue
            if recv_data.get("id") != self.device_id:
                log.debug("El mensaje no lleva la identificación de este dispositivo")
            if self.callback:
                try:
                    self.callback(recv_data)
                except Exception as e:
                    log.error("Excepción producida en el callback de recepción: "
                        f"({type(e).__name__}) {e}")
            self.lora_modem.calibrate_image() # prueba y mejora la sensibilidad de RX para la próxima recepción
