#!/usr/bin/env python3
# bleak
# rol Central

import asyncio
from bleak import BleakClient
from bleak import BleakScanner
import traceback

"""
def callback(sender, data):
    data_transf = data[:]
    print(f"{sender}: {data_transf}")
await client.start_notify('f4c70002-40c5-88cc-c1d6-77bfb6baf772', callback)
await asyncio.sleep(30)
await client.stop_notify('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
"""


"""
devices = await BleakScanner.discover()
for d in devices:
    print(d)
"""

address = "08:a6:f7:a1:8d:96"
MODEL_NBR_UUID = 'f4c70002-40c5-88cc-c1d6-77bfb6baf772'

async def main(address):

    print("Rutina principal")

    try:
        async with BleakClient(address) as client:

            print("BleakClient creado")

            value = await client.read_gatt_char('f4c70002-40c5-88cc-c1d6-77bfb6baf772')
            print("Valor de la caracteristica: ", value)
            print("Tipo recibido: ", type(value))
    except Exception as e:
            print(f"Ocurrió un error: {e}")
            traceback.print_exc()

        # Obtener la característica y sus propiedades
        # descriptor = await client.read_gatt_descriptor(BleakGATTDescriptor('f4c70002-40c5-88cc-c1d6-77bfb6baf772'))
        # print("Descriptor de la característica:", descriptor)



asyncio.run(main(address))
