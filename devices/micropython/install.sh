#!/usr/bin/env bash

cd $(dirname $0)/src
pwd

# Dependencias
mpremote mip install umqtt.simple

# Firmware
mpremote fs cp ota_client.py :main.py
mpremote fs cp thingsboard_device_utils.py :lib/thingsboard_device_utils.py

# Configuración
mpremote fs cp wifi_config.json :wifi_config.json
mpremote fs cp thingsboard_config.json :thingsboard_config.json
