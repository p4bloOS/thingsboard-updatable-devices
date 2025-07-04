#!/usr/bin/env bash

set -eux

cd $(dirname $0)
pwd

mpremote mkdir lib || true
mpremote cp src/external/thingsboard-micropython-client-sdk/{umqtt,sdk_utils,tb_device_mqtt,provision_client}.py :lib/

# Código fuente de este proyecto
mpremote cp src/boot.py :/
mpremote cp src/main.py :/
mpremote cp src/utils.py :lib/

# Configuración
mpremote mkdir config || true
mpremote cp config/* :config/

# Firmware metadata
mpremote cp src/FW_METADATA.json :/
