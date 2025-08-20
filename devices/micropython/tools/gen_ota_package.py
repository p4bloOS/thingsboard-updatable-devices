#!/usr/bin/env python3

import argparse
import tempfile
import subprocess
import os
import tarfile
import json


def create_ota_pkg(out_file_dir, out_file_name=None):

    with tempfile.TemporaryDirectory() as temp_dir:
        print("Copiando sistema de ficheros del dispositivo a un directorio temporal")
        cmd = ["mpremote", "cp", "-r", ":/", temp_dir]
        try:
            subprocess.run(
                cmd,
                check=True,
                text=True,
                capture_output=False
            )
        except subprocess.CalledProcessError as e:
            print("Error al ejecutar mpremote: ", e)
            return -1

        if out_file_name == None:
            fw_metadata_path = os.path.join(temp_dir, "FW_METADATA.json")
            with open(fw_metadata_path, 'r', encoding='utf-8') as archivo:
                fw_metadata = json.load(archivo)
            out_file_name = f"{fw_metadata['title']}_{fw_metadata['version']}.tar.gz"

        print("Creando archivo comprimido TAR GZ")
        out_file_path = os.path.join(out_file_dir, out_file_name)
        with tarfile.open(out_file_path, "w:gz", format=tarfile.GNU_FORMAT) as tar:
            tar.add(temp_dir, arcname="/")
        print(f"Archivo de salida creado: {out_file_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Genera, en el directorio tools/generated, un paquete OTA para "
            "MicroPython a partir del estado actual del dispositivo conectado con mpremote."
    )
    parser.add_argument(
        "-n", "--name", type=str, default=None,
        help="Nombre del archivo de salida (por defecto se forma a partir de la "
             "info. encontrada en FW_METADATA.json)"
    )
    args = parser.parse_args()

    this_script_dir = os.path.dirname(os.path.abspath(__file__))
    generated_dir = os.path.join(this_script_dir, "generated")
    if not os.path.exists(generated_dir):
        os.makedirs(generated_dir)

    create_ota_pkg(generated_dir, args.name)

if __name__ == "__main__":
    main()
