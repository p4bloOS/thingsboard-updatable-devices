#!/usr/bin/env bash

set -e
cd $(dirname $0)

connectivity_variant="wifi"
if [ -n "$1" ]; then
    connectivity_variant="$1"
fi

mpremote mip install ../mip_packages/thingsboard-ota-helpers.json
mpremote mip --target "" install "../mip_packages/example-${connectivity_variant}.json"
