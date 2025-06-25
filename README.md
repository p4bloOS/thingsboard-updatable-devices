# 01-minimum_iot_system

Un sistema IoT mínimo como primera toma de contacto con la plataforma Thingsboard y el entorno Micropython en la parte del dispositivo. El dispositivo es una placa de desarrollo con Micropython (ha sido robado con una ESP-32) que envía un número random a la plataforma cada 10 segundos. La plataforma muestra la evolución de dicho valor a lo largo del tiempo.

El dispositivo intentará conectarse a la red wifi cuyas credenciales se configuran en el fichero `devices/micropython/wifi_config.json`.

En el fichero `devices/micropython/thingsboard_config.json` se define la IP y el puerto del servidor Thingsboard, junto con el *access token* del dispositivo que previamente se ha de crear en la plataforma.

`platform/resources/simple_dashboard.json` contiene un panel importable desde Thingsboard con el cual se puede visualizar la variable emitida por el dispositivo.


---

## Plataforma

Levantar el contenedor de Thingsboard por primera vez:
```bash
cd TFG/platform
mkdir -p mytb-data && sudo chown -R 799:799 mytb-data
mkdir -p mytb-logs && sudo chown -R 799:799 mytb-logs
docker compose up -d
# interfaz web escuchando en http://localhost:8080/
```

Consultar los logs:
```bash
docker compose logs -f mytb
```

Detener/reanudar el contenedor:
```bash
docker compose stop mytb
docker compose start mytb
```

Credenciales predeterminadas de la interfaz web:

(usuario / contraseña)
- sysadmin@thingsboard.org / sysadmin
- tenant@thingsboard.org / tenant
- customer@thingsboard.org / customer

Para recibir recibir los datos del dispositivo, se puede crear en Thingsboard un dispositivo de nombre my-esp32-device.

---

## Dispositivo

*Probado en una placa ESP32-WROOM con Micropython instalado.*

Crear un entorno virtual de Python:
```bash
cd TFG/
python3 -m venv venv # crear entorno virtual
```

Configurar el "venv" para ayudar al LSP de nuestro IDE a captar las referencias:
```bash
site_packages_dir="$(./venv/bin/python -c "import site; print(site.getsitepackages()[0])")"
realpath devices/micropython/src/external/thingsboard-micropython-client-sdk/ \
> "${site_packages_dir}/tb-client-lib.pth"
./venv/bin/pip install micropython-esp32-stubs==1.24.1.post2
```

Instalar **mpremote**:
```bash
source py_venv/bin/activate
pip install mpremote
```

Instalar la dependencia **umqtt.simple** en el dispositivo:
```bash
mpremote mip install umqtt.simple
```

Instalar el programa principal en la placa:
```bash
cd TFG/devices/micropython
mpremote fs cp main.py :main.py
```

Subir los archivos de configuración al dispositivo:
```bash
mpremote fs cp wifi_config.json :wifi_config.json
mpremote fs cp thingsboard_config.json :thingsboard_config.json
```
