import asyncio
import gc
import machine
import bluetooth
import aioble
from hashlib import sha256

# TO-DO: introducir logging

DEVICE_NAME = "Micropython-updatable-thing"
CUSTOM_SERVICE_UUID = bluetooth.UUID('f4c70001-40c5-88cc-c1d6-77bfb6baf772')

# Características BLE para la aplicación (no han de entrar en conflicto con las del BleThingsboardOtaManager)
MEMFREE_CHARACTERISTIC_UUID          = bluetooth.UUID('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
MEMALLOC_CHARACTERISTIC_UUID         = bluetooth.UUID('f4c70003-40c5-88cc-c1d6-77bfb6baf772')
GC_COLLECT_RPC_CHARACTERISTIC_UUID   = bluetooth.UUID('f4c70004-40c5-88cc-c1d6-77bfb6baf772')


class BleThingsboardOtaManager:

    # Características BLE para la actualización OTA (atributos compartidos)
    FW_TITLE_CHARACTERISTIC_UUID         = bluetooth.UUID('f4c70005-40c5-88cc-c1d6-77bfb6baf772')
    FW_VERSION_CHARACTERISTIC_UUID       = bluetooth.UUID('f4c70006-40c5-88cc-c1d6-77bfb6baf772')
    FW_SIZE_CHARACTERISTIC_UUID          = bluetooth.UUID('f4c70007-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_CHARACTERISTIC_UUID      = bluetooth.UUID('f4c70008-40c5-88cc-c1d6-77bfb6baf772')
    FW_CHECKSUM_ALG_CHARACTERISTIC_UUID  = bluetooth.UUID('f4c70009-40c5-88cc-c1d6-77bfb6baf772')

    # Características BLE para la actualización OTA (telemetría)
    CURRENT_FW_TITLE_CHARACTERISTIC_UUID    = bluetooth.UUID('f4c7000a-40c5-88cc-c1d6-77bfb6baf772')
    CURRENT_FW_VERSION_CHARACTERISTIC_UUID  = bluetooth.UUID('f4c7000b-40c5-88cc-c1d6-77bfb6baf772')
    FW_STATE_CHARACTERISTIC_UUID            = bluetooth.UUID('f4c7000c-40c5-88cc-c1d6-77bfb6baf772')
    FW_ERROR_CHARACTERISTIC_UUID            = bluetooth.UUID('f4c7000f-40c5-88cc-c1d6-77bfb6baf772')

    # Característica para distinguir el tipo de OTA
    OTA_CONNECTIVITY_CHARACTERISTIC_UUID    = bluetooth.UUID('f4c7000d-40c5-88cc-c1d6-77bfb6baf772')

    # Característica sobre la cual recibir el firmware por fragmentos
    FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID = bluetooth.UUID('f4c7000e-40c5-88cc-c1d6-77bfb6baf772')


    def __init__(self, ble_service: aioble.Service):

        # Telemtría sobre el estado de la OTA
        self.current_fw_title_char = aioble.Characteristic(ble_service, self.CURRENT_FW_TITLE_CHARACTERISTIC_UUID, read=True)
        self.current_fw_version_char = aioble.Characteristic(ble_service, self.CURRENT_FW_VERSION_CHARACTERISTIC_UUID, read=True)
        self.fw_state_char = aioble.Characteristic(ble_service, self.FW_STATE_CHARACTERISTIC_UUID, read=True)
        self.fw_error_char = aioble.Characteristic(ble_service, self.FW_ERROR_CHARACTERISTIC_UUID, read=True)

        # Atributos compartidos para la actuaización OTA
        self.fw_title_char = aioble.BufferedCharacteristic(ble_service, self.FW_TITLE_CHARACTERISTIC_UUID, write=True, capture=True, max_len=64)
        self.fw_version_char = aioble.Characteristic(ble_service, self.FW_VERSION_CHARACTERISTIC_UUID, write=True, capture=True)
        self.fw_size_char = aioble.Characteristic(ble_service, self.FW_SIZE_CHARACTERISTIC_UUID, write=True,capture=True)
        self.fw_checksum_char = aioble.BufferedCharacteristic(ble_service, self.FW_CHECKSUM_CHARACTERISTIC_UUID, write=True, capture=True, max_len=64)
        self.fw_checksum_alg_char = aioble.Characteristic(ble_service, self.FW_CHECKSUM_ALG_CHARACTERISTIC_UUID, write=True, capture=True)

        # Atributo "ota_connectivity" para que la Rule Chain distinga el tipo de OTA
        self.ota_connectivity_char = aioble.Characteristic(ble_service, self.OTA_CONNECTIVITY_CHARACTERISTIC_UUID, read=True)

        # Característica sobre la cual recibir el firmware por fragmentos
        self.firmware_fragment_char = aioble.BufferedCharacteristic(ble_service, self.FIRMWARE_FRAGMENT_CHARACTERISTIC_UUID, write=True, capture=True, max_len=128)


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
        print(f"Esperando recibir {fw_size} bytes de firmware")
        fw_data = bytearray()
        bytes_received = 0
        while bytes_received < fw_size:
            _, fw_fragment = await self.firmware_fragment_char.written()
            fw_data.extend(fw_fragment)
            bytes_received = bytes_received + len(fw_fragment)
        return fw_data


    def _verify_checksum(self, firmware_data, checksum_alg, checksum):
        checksum_of_received_firmware = None
        print('Checksum algorithm is: %s' % checksum_alg)
        if checksum_alg.lower() == "sha256":
            checksum_of_received_firmware = "".join(["%.2x" % i for i in sha256(firmware_data).digest()])
        else:
            print('Client error. Unsupported checksum algorithm.')
        print(checksum_of_received_firmware)
        return checksum_of_received_firmware == checksum


    async def manage_OTA_procedure_loop(self):
        """
        Itera infinitamente sobre el procedimiento de la OTA.
        """
        while True:
            await self._manage_OTA_procedure()


    async def _manage_OTA_procedure(self):
        """
        Maneja el procedimiento de la OTA.
        """

        self.ota_connectivity_char.write("BLE".encode('utf-8'))

        (fw_title, fw_version, fw_size, fw_checksum, fw_checksum_alg
            ) = await self._wait_for_OTA_startup()
        print(f"Actualización iniciada desde Thingsboard: "
              f"fw_title={fw_title}, "
              f"fw_version={fw_version}, "
              f"fw_size={fw_size}, "
              f"fw_checksum={fw_checksum}, "
              f"fw_checksum_alg={fw_checksum_alg}"
        )

        # TO-DO: Comprobar si hace falta una actualización

        # Reportar el estado DOWNLOADING
        # (al recibirlo en Thingsboard, el rule chain activará ls transferencia de la OTA)
        self.current_fw_title_char.write("micropython-OTA-client".encode('utf-8'))
        self.current_fw_version_char.write("v1".encode('utf-8'))
        self.fw_state_char.write("DOWNLOADING".encode('utf-8'))

        # Recibir el firmware y a continuación reportar el estado DOWNLOADED
        print("En espera de recibir el nuevo firmware")
        fw_data = await self._receive_firmware_data()
        print("Se ha recibido el firmware")
        self.fw_state_char.write("DOWNLOADED".encode('utf-8'))

        # Verificación del firmware recibido
        if not self._verify_checksum(fw_data, fw_checksum_alg, fw_checksum):
            self.fw_state_char.write("FAILED".encode('utf-8'))
            error_msg = "No se ha podido verificar el checksum"
            print(error_msg)
            self.fw_error_char.write(error_msg)
            return
        self.fw_state_char.write("VERIFIED".encode('utf-8'))

        # TO-DO: Guardar el firmware en el archivo correspondiente
        print("Ahora se procedería a la actualización")

        # Reiniciar


async def memory_report(
    period_ms,
    mem_free_char: aioble.Characteristic,
    mem_alloc_char: aioble.Characteristic
):
    """
    Envía telemetría a la plataforma con datos sobre la memoria del heap
    asignada y libre.
    """
    while True:
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        mem_free_char.write(str(mem_free).encode('utf-8'), send_update=True)
        mem_alloc_char.write(str(mem_alloc).encode('utf-8'), send_update=True)
        # print("mem_free: ", mem_free, "; mem_alloc: ", mem_alloc)
        await asyncio.sleep_ms(period_ms)


async def listen_gc_collect_rpc( gc_collect_char: aioble.Characteristic ):
    """
    Insetar coment
    """
    while True:
        await gc_collect_char.written()
        print("RPC recibido")
        gc.collect()
        gc_collect_char.write("Done".encode('utf-8'))



async def advertise_service():
    """
    Insertar coment
    """
    ADV_INTERVAL_US = const(250000)
    GENERIC_DEVICE_APPEARANCE = const(0)
    while True:
        connection = await aioble.advertise(
                ADV_INTERVAL_US,
                name=DEVICE_NAME,
                services=[CUSTOM_SERVICE_UUID],
                appearance=GENERIC_DEVICE_APPEARANCE,
                manufacturer=(0xabcd, b"1234"),
            )
        print("Connection from", connection.device)


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


async def main():
    """
    Inicializa el rol Peropheral de BLE y ejecuta concurrentemente las tareas
    asíncronas definidas.
    """
    addr = aioble.config("mac")
    print("Dirección MAC de BLE: ", addr[1])

    # aioble.config(mtu=64)

    custom_service = aioble.Service(CUSTOM_SERVICE_UUID)

    mem_free_char = aioble.Characteristic(custom_service, MEMFREE_CHARACTERISTIC_UUID, read=True, notify=True)
    mem_alloc_char = aioble.Characteristic(custom_service, MEMALLOC_CHARACTERISTIC_UUID, read=True, notify=True)
    gc_collect_char = aioble.Characteristic(custom_service, GC_COLLECT_RPC_CHARACTERISTIC_UUID, write=True)

    ota_manager = BleThingsboardOtaManager(custom_service)

    aioble.register_services(custom_service)

    await asyncio.gather(
        advertise_service(),
        memory_report(1_000, mem_free_char, mem_alloc_char),
        listen_gc_collect_rpc(gc_collect_char),
        heartbeat_LED(),
        ota_manager.manage_OTA_procedure_loop()
    )


if __name__ == "__main__":
    """
    Punto de entrada al programa principal
    """
    asyncio.run(main())
