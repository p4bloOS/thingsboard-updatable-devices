import logging
import asyncio
from hashlib import sha256
from machine import reset
from gc import collect as gc_collect
from json import dumps as json_dumps, loads as json_loads
from network import WLAN, STA_IF
from ubinascii import hexlify
from collections import deque


log = logging.getLogger("updatable_lora_node")
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA


class UpdatableLoraNode():

    MAX_RETRIES = 4
    ACK_MAX_COUNT = 100

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
        self.received_acks = set() # Lista de identificadores de ACKs recibidos
        self.ack_counter = 0 # Contador circular entre 0 y 99 para identificar el próximo ACK
        # Cola para evitar tratar varias veces un mensaje que se puede reenviar
        self.last_reliable_msgs_received = deque([], 10)


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
        self.lora_modem.calibrate() # Calibración inicial para oscilador RC, PLL y ADC
        await self.reliable_send("connect", {})
        connectivity_attrs = {"ota_connectivity": "LoRa", "lora_id": self.device_id}
        await self.reliable_send("attributes", connectivity_attrs)


    async def send(self, subtopic, msg):
        msg_bytes = json_dumps({
            "id": f"{self.device_id}/{subtopic}",
            "msg": msg
        }).encode("utf-8")
        await self.lora_modem.send(msg_bytes)


    async def reliable_send(self, subtopic, msg):
        ack_count = self.ack_counter
        msg_bytes = json_dumps({
            "id": f"{self.device_id}/reliable/{subtopic}",
            "msg": msg,
            "count": ack_count
        }).encode("utf-8")
        log.debug(f"Enviando mensaje fiable: {msg_bytes}")
        self.ack_counter = (self.ack_counter + 1) % self.ACK_MAX_COUNT
        success = False
        for tries in range(self.MAX_RETRIES):
            log.debug(f"Envío de mensaje fiable, intento {tries}")
            await self.lora_modem.send(msg_bytes)
            await asyncio.sleep(5)
            log.debug(f"Estado de received_acks: {self.received_acks}" )
            if ack_count in self.received_acks:
                self.received_acks.remove(ack_count)
                log.debug("Mensaje confirmado")
                success = True
                break
        if not success:
            log.error("No se ha obtenido ACK. Mensaje descartado")

        self.lora_modem.calibrate_image() # prueba y mejora la sensibilidad de RX para la próxima recepción


    def set_callback(self, callback):
        """
        Establece la función de callback que se llamará más tarde.

        :param callback: Función que se usará como callback.
        """
        self.callback = callback
        log.debug("Callback de recepción de mensajes establecido.")


    async def _manage_ota(self, msg_data):
        # Manejar el estado con attrbutos del objeto


        # Cuando hay que recibir el firmware nos ponemos a escuchar en modo síncrono
        # El primer mensaje es el tamaño
        # El resto son los fragmentos de firmW. Se reciben por orden.
        log.debug("")


    async def _handle_msg_data(self, msg_data):

        ack_count = msg_data.get('ack')
        required_ack_count = msg_data.get('requires_ack')

        # El mensaje es un ACK
        if ack_count != None:
            self.received_acks.add(ack_count)
            return

        # El mensaje requiere confirmación
        elif required_ack_count != None:
            await self.send("ack", {"count": required_ack_count})
            if required_ack_count in self.last_reliable_msgs_received:
                log.debug("El mensaje ya ha sido tratado")
                return
            else:
                self.last_reliable_msgs_received.append(required_ack_count)

        # Manejo de un
        await self._manage_ota(msg_data)

        # Callback establecido por el usuario
        if self.callback:
            try:
                self.callback(msg_data)
            except Exception as e:
                log.error("Excepción producida en el callback de recepción: "
                    f"({type(e).__name__}) {e}")


    async def listen(self):
        log.info("A la escucha de mensajes LoRa")
        async for rx in self.lora_modem.recv_continuous():
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
                continue
            await self._handle_msg_data(recv_data)
