import logging
from asyncio import sleep_ms as asyncio_sleep_ms, create_task as asyncio_create_task
from hashlib import sha256
from machine import reset
from gc import collect as gc_collect
from json import dumps as json_dumps, loads as json_loads
from binascii import a2b_base64
from network import WLAN, STA_IF
from ubinascii import hexlify
from collections import deque


log = logging.getLogger("updatable_lora_node")
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA


class UpdatableLoraNode():

    MAX_RETRIES = 15
    ACK_MAX_COUNT = 100
    RETRY_TIMEOUT_MS = 1000

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
        self.fw_title              = None
        self.fw_version            = None
        self.fw_size               = None
        self.fw_checksum           = None
        self.fw_checksum_algorithm = None
        self.downloading_firmware = False
        self.fw_bin_data = bytearray()
        self.bytes_received = 0


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
            await self.lora_modem.send(msg_bytes)
            await asyncio_sleep_ms(self.RETRY_TIMEOUT_MS)
            if ack_count in self.received_acks:
                self.received_acks.remove(ack_count)
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


    def _read_fw_attrs(self, msg_data) -> bool:

        if "fw_title" in msg_data:
            self.fw_title = msg_data["fw_title"]
        if "fw_version" in msg_data:
            self.fw_version = msg_data["fw_version"]
        if "fw_size" in msg_data:
            self.fw_size = int(msg_data["fw_size"])
        if "fw_checksum" in msg_data:
            self.fw_checksum = msg_data["fw_checksum"]
        if "fw_checksum_algorithm" in msg_data:
            self.fw_checksum_algorithm = msg_data["fw_checksum_algorithm"]

        if (self.fw_title != None and self.fw_version != None and
            self.fw_size != None and self.fw_checksum != None and
            self.fw_checksum_algorithm != None
        ):
            log.info("Actualización iniciada desde Thingsboard: "
                  f"fw_title={self.fw_title}, "
                  f"fw_version={self.fw_version}, "
                  f"fw_size={self.fw_size}, "
                  f"fw_checksum={self.fw_checksum}, "
                  f"fw_checksum_algorithm={self.fw_checksum_algorithm}"
            )
            return True
        else:
            return False


    def _clean_ota_status(self):
        self.fw_title              = None
        self.fw_version            = None
        self.fw_size               = None
        self.fw_checksum           = None
        self.fw_checksum_algorithm = None


    async def _handle_fw_download(self, msg_data):

         # Transferencia del firmware
        try:
            if "fw_fragment" in msg_data:
                self.fw_str_fragment = msg_data["fw_fragment"]
                self.fw_bin_fragment = a2b_base64(self.fw_str_fragment)
                self.fw_bin_data.extend(self.fw_bin_fragment)
                self.bytes_received = self.bytes_received + len(self.fw_bin_fragment)
                log.debug(f"Descargando... {self.bytes_received}/{self.fw_size}B")
        except Exception as e:
            error_msg = "Excepción producida durante la recepción del paquete de OTA: " + \
                f"({type(e).__name__}) {e}"
            log.error(error_msg)
            failed_telemetry = {
                "fw_state": "FAILED", "fw_error": error_msg
            }
            asyncio_create_task(self.reliable_send("telemetry", failed_telemetry ))
            self.downloading_firmware = False
            self._clean_ota_status()
            return

        if self.bytes_received != self.fw_size:
            # Aún faltan fragmentos por recibir
            return

        # Descarga completada
        log.info("Todo el firmware ha sido recibido")
        downloaded_telemetry = { "fw_state": "DOWNLOADED"}
        asyncio_create_task(self.reliable_send("telemetry", downloaded_telemetry ))
        self.downloading_firmware = False

        # Verificación del firmware recibido
        if not self._verify_checksum(self.fw_bin_data, self.fw_checksum_algorithm, self.fw_checksum):
            error_msg = "No se ha podido verificar el checksum"
            log.error(error_msg)
            failed_telemetry = {
                "fw_state": "FAILED", "fw_error": error_msg
            }
            asyncio_create_task(self.reliable_send("telemetry", failed_telemetry ))
            self._clean_ota_status()
            return
        verified_telemetry = { "fw_state": "VERIFIED"}
        asyncio_create_task(self.reliable_send("telemetry", verified_telemetry ))
        await asyncio_sleep_ms(4000) # Espera a que sea lea el estado verified

        # Guardar el firmware en el archivo correspondiente
        with open(self.fw_filename, "wb") as firmware_file:
            firmware_file.write(self.fw_bin_data)
        log.info(f"El paquete de firmware recibido se ha guardado en {self.fw_filename}")

        # Guardar los metadatos esperados del firmware recibido
        metadata_file_name = self.fw_filename + EXPECTED_METADATA_SUFFIX
        with open(metadata_file_name, "wb") as firmware_metadata_file:
            firmware_metadata_file.write(
                json_dumps({ "title": self.fw_title, "version": self.fw_version })
            )
        log.debug(f"Los metadatos del paquete se han guardado en {metadata_file_name}")

        log.info("Reiniciando sistema para instalar nuevo paquete de firmware")
        reset()


    async def _manage_ota(self, msg_data):

        if self.downloading_firmware:
            await self._handle_fw_download(msg_data)

        else:

            if not self._read_fw_attrs(msg_data):
                return

            # En este punto se ha inicado la OTA desde Thignsboard
            # Se comprueba si es necesaria la actualización
            if (self.fw_current_title == self.fw_title and
                self.fw_current_version == self.fw_version
            ):
                log.warning("El firmware indicado desde Thingsboard ya está instalado")
                updated_state_telemetry = { "fw_state" : "UPDATED" }
                asyncio_create_task(self.reliable_send("telemetry", updated_state_telemetry ))
                self._clean_ota_status()
                return

            # Reportar el estado DOWNLOADING
            # (al recibirlo en Thingsboard, el rule chain activará ls transferencia de la OTA)
            downloading_state_telemetry = { "fw_state" : "DOWNLOADING" }
            asyncio_create_task(self.reliable_send("telemetry", downloading_state_telemetry ))
            self.downloading_firmware = True
            log.info("Esperando transferencia de firmware")



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
                # log.debug("El mensaje ya ha sido tratado")
                return
            else:
                self.last_reliable_msgs_received.append(required_ack_count)

        # Manejo de una posible actualización OTA
        await self._manage_ota(msg_data)

        # Callback establecido por el usuario
        if self.callback and not self.downloading_firmware:
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
