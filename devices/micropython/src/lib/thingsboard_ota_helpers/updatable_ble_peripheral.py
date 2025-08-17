import aioble
import logging
from hashlib import sha256
from machine import reset
from bluetooth import UUID as bluetooth_UUID
from asyncio import Event as asyncio_Event
from gc import collect as gc_collect
from json import dumps as json_dumps

log = logging.getLogger("updatable_ble_peripheral")
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA

class UpdatableBLEPeripheral():

    DEVICE_NAME = "Micropython-updatable-thing"
    CUSTOM_SERVICE_UUID = bluetooth_UUID('f4c70001-40c5-88cc-c1d6-77bfb6baf772')

    # Características BLE para la actualización OTA (atributos compartidos)
    FW_TITLE_CHARACTERISTIC_UUID         = bluetooth_UUID('f4c70005-40c5-88cc-c1d6-77bfb6baf772')
    FW_VERSION_CHARACTERISTIC_UUID       = bluetooth_UUID('f4c70006-40c5-88cc-c1d6-77bfb6baf772')
    FW_SIZE_CHARACTERISTIC_UUID          = bluetooth_UUID('f4c70007-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_CHARACTERISTIC_UUID      = bluetooth_UUID('f4c70008-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_ALG_CHARACTERISTIC_UUID  = bluetooth_UUID('f4c70009-40c5-88cc-c1d6-77bfb6baf772')

    # Características BLE para la actualización OTA (telemetría)
    CURRENT_FW_TITLE_CHARACTERISTIC_UUID    = bluetooth_UUID('f4c7000a-40c5-88cc-c1d6-77bfb6baf772')
    CURRENT_FW_VERSION_CHARACTERISTIC_UUID  = bluetooth_UUID('f4c7000b-40c5-88cc-c1d6-77bfb6baf772')
    FW_STATE_CHARACTERISTIC_UUID            = bluetooth_UUID('f4c7000c-40c5-88cc-c1d6-77bfb6baf772')
    FW_ERROR_CHARACTERISTIC_UUID            = bluetooth_UUID('f4c7000f-40c5-88cc-c1d6-77bfb6baf772')

    # Característica para distinguir el tipo de OTA
    OTA_CONNECTIVITY_CHARACTERISTIC_UUID    = bluetooth_UUID('f4c7000d-40c5-88cc-c1d6-77bfb6baf772')

    # Característica sobre la cual recibir el firmware por fragmentos
    FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID = bluetooth_UUID('f4c7000e-40c5-88cc-c1d6-77bfb6baf772')


    class FirmwareStateCharacteristic(aioble.Characteristic):

        fw_state_read_event = asyncio_Event()
        def on_read(self, connection):
            # log.debug("Característica de tipo fw_state leída desde Thingsboard")
            self.fw_state_read_event.set()
            return 0


    def __init__(self,
        fw_current_title="Initial",
        fw_current_version="v0",
        fw_filename="new_firmware.tar.gz"
    ):
        self.fw_current_title = fw_current_title
        self.fw_current_version = fw_current_version
        self.fw_filename = fw_filename

        address = aioble.config("mac")
        log.info(f"Dirección MAC del módulo BLE: {address[1]}")

        self.ble_service = aioble.Service(self.CUSTOM_SERVICE_UUID)

        # Telemtría sobre el estado de la OTA
        self.current_fw_title_char = aioble.Characteristic(self.ble_service, self.CURRENT_FW_TITLE_CHARACTERISTIC_UUID, read=True)
        self.current_fw_version_char = aioble.Characteristic(self.ble_service, self.CURRENT_FW_VERSION_CHARACTERISTIC_UUID, read=True)
        self.fw_state_char = self.FirmwareStateCharacteristic(self.ble_service, self.FW_STATE_CHARACTERISTIC_UUID, read=True)
        self.fw_error_char = aioble.BufferedCharacteristic(self.ble_service, self.FW_ERROR_CHARACTERISTIC_UUID, read=True, max_len=128)

        # Atributos compartidos para la actuaización OTA
        self.fw_title_char = aioble.BufferedCharacteristic(self.ble_service, self.FW_TITLE_CHARACTERISTIC_UUID, write=True, capture=True, max_len=64)
        self.fw_version_char = aioble.Characteristic(self.ble_service, self.FW_VERSION_CHARACTERISTIC_UUID, write=True, capture=True)
        self.fw_size_char = aioble.Characteristic(self.ble_service, self.FW_SIZE_CHARACTERISTIC_UUID, write=True,capture=True)
        self.fw_checksum_char = aioble.BufferedCharacteristic(self.ble_service, self.FW_CHECKSUM_CHARACTERISTIC_UUID, write=True, capture=True, max_len=64)
        self.fw_checksum_alg_char = aioble.Characteristic(self.ble_service, self.FW_CHECKSUM_ALG_CHARACTERISTIC_UUID, write=True, capture=True)

        # Atributo "ota_connectivity" para que la Rule Chain distinga el tipo de OTA
        self.ota_connectivity_char = aioble.Characteristic(self.ble_service, self.OTA_CONNECTIVITY_CHARACTERISTIC_UUID, read=True)

        # Característica sobre la cual recibir el firmware por fragmentos
        self.firmware_fragment_char = aioble.BufferedCharacteristic(self.ble_service, self.FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID, write=True, capture=True, max_len=128)


    async def _wait_for_OTA_startup(self):
        """
        Espera al estado INITIATED en Thingsboard y devuelve una tupla de str
        (fw_title, fw_version, fw_size, fw_checksum, fw_checksum_alg)
        """
        _ , data = await self.fw_title_char.written()
        fw_title = data.decode('utf-8')
        _ , data = await self.fw_version_char.written()
        fw_version = data.decode('utf-8')
        _ , data = await self.fw_size_char.written()
        fw_size = data.decode('utf-8')
        _ , data = await self.fw_checksum_char.written()
        fw_checksum = data.decode('utf-8')
        _ , data = await self.fw_checksum_alg_char.written()
        fw_checksum_alg = data.decode('utf-8')
        return(fw_title, fw_version, fw_size, fw_checksum, fw_checksum_alg)


    async def _receive_firmware_data(self):
        """
        Recibe y retorna el firmware en fragmentos, través de la característica BLE
        dedicada a ello.
        """
        _, coded_fw_size = await self.firmware_fragment_char.written()
        fw_size = int.from_bytes(coded_fw_size, 'big')
        log.debug(f"Esperando recibir {fw_size} bytes de firmware")
        gc_collect()
        fw_data = bytearray()
        bytes_received = 0
        while bytes_received < fw_size:
            _, fw_fragment = await self.firmware_fragment_char.written()
            fw_data.extend(fw_fragment)
            bytes_received = bytes_received + len(fw_fragment)
        return fw_data


    def _verify_checksum(self, firmware_data, checksum_alg, checksum):
        checksum_of_received_firmware = None
        if checksum_alg.lower() == "sha256":
            checksum_of_received_firmware = "".join(["%.2x" % i for i in sha256(firmware_data).digest()])
        else:
            log.error("Algoritmo de checksum no soportado (solo SHA256)")
        log.debug(f"Checksum del firmware recibido: {checksum_of_received_firmware}")
        return checksum_of_received_firmware == checksum


    async def _manage_OTA_update(self):
        """
        Maneja el procedimiento de la OTA.
        """

        self.ota_connectivity_char.write("BLE".encode('utf-8'))
        self.current_fw_title_char.write(self.fw_current_title.encode('utf-8'))
        self.current_fw_version_char.write(self.fw_current_version.encode('utf-8'))

        # Esperar al inicio de la OTA desde Thingsboard
        (fw_title, fw_version, fw_size, fw_checksum, fw_checksum_alg
            ) = await self._wait_for_OTA_startup()
        log.info("Actualización iniciada desde Thingsboard: "
              f"fw_title={fw_title}, "
              f"fw_version={fw_version}, "
              f"fw_size={fw_size}, "
              f"fw_checksum={fw_checksum}, "
              f"fw_checksum_alg={fw_checksum_alg}"
        )

        # Comprobar si es necesaria la actualización
        if (self.fw_current_title == fw_title and
            self.fw_current_version == fw_version
        ):
            log.warning("El firmware recibido desde Thingsboard ya está instalado")
            self.fw_state_char.write("UPDATED".encode('utf-8'))
            return

        # Reportar el estado DOWNLOADING
        # (al recibirlo en Thingsboard, el rule chain activará ls transferencia de la OTA)
        self.fw_state_char.write("DOWNLOADING".encode('utf-8'))

        # Recibir el firmware y a continuación reportar el estado DOWNLOADED
        log.debug("En espera de recibir el nuevo firmware")
        try:
            fw_data = await self._receive_firmware_data()
        except Exception as e:
            error_msg = "Excepción producida durante la recepción del paquete de OTA: " + \
                f"({type(e).__name__}) {e}"
            log.error(error_msg)
            self.fw_state_char.write("FAILED".encode('utf-8'))
            self.fw_error_char.write(error_msg.encode('utf-8'))
            return
        log.debug("Se ha recibido el firmware")
        self.fw_state_char.write("DOWNLOADED".encode('utf-8'))

        # Verificación del firmware recibido
        if not self._verify_checksum(fw_data, fw_checksum_alg, fw_checksum):
            error_msg = "No se ha podido verificar el checksum"
            log.error(error_msg)
            self.fw_state_char.write("FAILED".encode('utf-8'))
            self.fw_error_char.write(error_msg.encode('utf-8'))
            return
        self.fw_state_char.write("VERIFIED".encode('utf-8'))
        self.fw_state_char.fw_state_read_event.clear()
        log.debug("Esperando a que sea leído el estado VERIFIED")
        await self.fw_state_char.fw_state_read_event.wait()

        # Guardar el firmware en el archivo correspondiente
        with open(self.fw_filename, "wb") as firmware_file:
            firmware_file.write(fw_data)
        log.info(f"El paquete de firmware recibido se ha guardado en {self.fw_filename}")

        # Guardar los metadatos esperados del firmware recibido
        metadata_file_name = self.fw_filename + EXPECTED_METADATA_SUFFIX
        with open(metadata_file_name, "wb") as firmware_metadata_file:
            firmware_metadata_file.write(
                json_dumps({ "title": fw_title, "version": fw_version })
            )
        log.debug(f"Los metadatos del paquete se han guardado en {metadata_file_name}")

        await self.disconnect()

        log.info("Reiniciando sistema para instalar nuevo paquete de firmware")
        reset()


    def register_service(self):
        aioble.register_services(self.ble_service)


    async def advertise_service(self):
        """
        Insertar coment
        """
        ADV_INTERVAL_US = const(250000)
        GENERIC_DEVICE_APPEARANCE = const(0)
        connection = await aioble.advertise(
            ADV_INTERVAL_US,
            name=self.DEVICE_NAME,
            services=[self.CUSTOM_SERVICE_UUID],
            appearance=GENERIC_DEVICE_APPEARANCE,
            manufacturer=(0xabcd, b"1234"),
        )
        log.info(f"Conexión desde {connection.device}")
        return connection


    async def run_advertising(self):
        """
        Insertar coment
        """
        log.info("Publicitando servicio BLE")
        while True:
            self.connection = await self.advertise_service()


    async def run_OTA_manager(self):
        """
        Itera infinitamente sobre el procedimiento de la OTA.
        """
        while True:
            log.debug("Manejador de OTAs a la escucha")
            await self._manage_OTA_update()


    async def disconnect(self):
        log.debug("Desconectando del cliente BLE")
        self.connection.disconnect()
