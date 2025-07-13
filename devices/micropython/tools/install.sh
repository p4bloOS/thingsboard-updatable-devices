#!/usr/bin/env bash

set -eu

cd $(dirname $0)

mpremote mip install ../mip_packages/ota-helper-lib.json
mpremote mip --target "" install ../mip_packages/example-program.json
