# 02-basic_ota_update

Implementación de una actualización OTA en un dispositivo con Micropython, usando Thingsboard como plataforma, a la cual se conecta el dispositivo a través de wifi y MQTT.

#### Configuración en `devices/micropython/config`:
- `network_config.json` : El dispositivo intentará conectarse a la red wifi cuyas credenciales se configuran en este fichero.
- `thingsboard_config.json` : Se define la IP y el puerto del servidor Thingsboard, junto con el *access token* del dispositivo que previamente se ha de crear en la plataforma.
- `ota_config.json` : algunas variables que definen la forma de aplicar la OTA.


---

## Plataforma

Clonar este repositorio, entrar en él y bajar sus submódulos
```bash
git clone -b 02-basic_ota_update https://github.com/p4bloOS/TFG.git
cd TFG/
git submodule update --init --recursive
```

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
realpath devices/micropython/src/external/tb-client-sdk/ \
> "${site_packages_dir}/tb-client-lib.pth"
realpath devices/micropython/src/lib/ > "${site_packages_dir}/my-lib.pth"
./venv/bin/pip install micropython-esp32-stubs==1.24.1.post2
```

Instalar **mpremote**:
```bash
source py_venv/bin/activate
pip install mpremote
```

Editar los archivos de configuración del directorio config:
- ota_config.json
- thingsboard_config.json
- wifi_config.json

Borrar todo todos los ficheros existentes en el dispositivo:
```bash
mpremote rm -rv :/
```

Instalar el proyecto en la placa:
```bash
./devices/micropython/install.sh
```

Actualizar los archivos de configuración:
```bash
mpremote fs cp devices/micropython/config/* :config/
mpremote fs cp devices/micropython/config/* :config/
```
