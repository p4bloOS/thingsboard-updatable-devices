#!/usr/bin/env bash

set -eu

cd $(dirname $0)

# Dependencias
mpremote mkdir lib || true
mpremote cp src/external/thingsboard-micropython-client-sdk/{umqtt,sdk_utils,tb_device_mqtt,provision_client}.py :lib/
mpremote mip install package.json

# Código fuente de este proyecto
mpremote cp src/boot.py :/
mpremote cp src/main.py :/
mpremote cp src/lib/utils.py :lib/

# Configuración
mpremote mkdir config || true
mpremote cp config/* :config/

# Firmware metadata
mpremote cp src/FW_METADATA.json :/
