# thingsboard-updatable-devices

Este un proyecto pretende implementar la actualización OTA en dispositivos IoT para la plataforma Thingsboard, concretamente en 2 clases de dispositvos:
- Microcontrolador con Micropython
- Mini-PC con Linx (Yocto Linux ????)

Se tratará de implementar el sistema sobre 3 escenarios de conectividad:
- TCP/IP
- BLE
- LoRa

Ramas de características desarrolladas hasta la fecha:
- [x] 01-minimum_iot_system
- [x] 02-basic_ota_update
- [x] 03-improved_ota_update
- [ ] 04-ble_support
- [ ] 05-lora_support
- [ ] 06-adaptation_to_linux


## Características relevantes

### Para **Micropython** ([thingsboard-updatable-devices/devices/micropython/](https://github.com/p4bloOS/thingsboard-updatable-devices/tree/master/devices/micropython)):

- Biblioteca **ota-helper**, capaz de gestionar la comunicación con Thingsboard relativa a las actualizaciones OTA y aplicar un paquete OTA sobre el sistema de ficheros de micropython.
- Aplicación de ejemplo para un dispositivo cliente de Thingsboard, actualizable y capaz de realizar otras tareas concurrentemente.
- Paquetes [mip](https://docs.micropython.org/en/latest/reference/packages.html) relativos a las 2 características anteriores. Véase:
    - [ota-helper-lib.json](https://github.com/p4bloOS/thingsboard-updatable-devices/blob/master/devices/micropython/mip_packages/ota-helper-lib.json)
    - [example-program.json](https://github.com/p4bloOS/thingsboard-updatable-devices/blob/master/devices/micropython/mip_packages/example-program.json)
- Herramienta [gen_ota_package.py](https://github.com/p4bloOS/thingsboard-updatable-devices/blob/master/devices/micropython/tools/gen_ota_package.py) para generar paquetes de actualización OTA en formato **tar.gz**.


### Para **Linux embebido** ([thingsboard-updatable-devices/devices/linux/](https://github.com/p4bloOS/thingsboard-updatable-devices/tree/master/devices/linux)) (*POR IMPLEMENTAR*):

- Adaptación a Python estándar sobre Linux de la biblioteca ota-helper y el programa de ejemplo.
- Imagen personalizada de Linux creada con [Buildroot](https://buildroot.org/), que contiene un servicio para comunicarse con Thingsboard y aplicar las actualizaciones mediante [RAUC](https://rauc.io/)
- Posibles herramientas por definir.

### Conectividad:

- Este proyecto funciona por defecto cuando el dispositivo se conecta directamente por MQTT a la plataforma o a alguno de sus gateways.
- Soporte para **BLE**: *POR IMPLEMENTAR*
- Soporte para **LoRa**: *POR IMPLEMENTAR*


---

## Instalación


### Plataforma

Clonar este repositorio, entrar en él y bajar sus submódulos
```bash
git clone https://github.com/p4bloOS/thingsboard-updatable-devices.git
cd thingsboard-updatable-devices/
git submodule update --init --recursive
```

Levantar el contenedor de Thingsboard por primera vez:
```bash
cd platform
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


## Dispositivo





*Probado en una placa ESP32-WROOM con Micropython instalado.*

Crear un entorno virtual de Python:
```bash
cd thingsboard-updatable-devices/
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

### Paquete mip **ota-helper-lib**:
  Contiene la biblioteca ota_helper.py y sus dependencias.
```bash
mpremote mip install mip_packages/ota-helper-lib.json
```

### Paquete mip **example-program**
Contiene los scripts que conforman un programa de ejemplo que realiza una actualización,
junto con los archivos de configuración que usan dichos scripts.
```bash
mpremote mip --target "" install mip_packages/example-program.json
```

Borrar todo todos los ficheros existentes en el dispositivo:
```bash
mpremote rm -rv :/
```


---

## Configuración

### Plataforma


AÑADIR LOS RESOURCES

Para recibir los datos del dispositivo, se puede crear en Thingsboard un dispositivo de nombre my-esp32-device.


### Dispositivo

#### Configuración en `devices/micropython/config`:
- `network_config.json` : El dispositivo intentará conectarse a la red wifi cuyas credenciales se configuran en este fichero.
- `thingsboard_config.json` : Se define la IP y el puerto del servidor Thingsboard, junto con el *access token* del dispositivo que previamente se ha de crear en la plataforma.
- `ota_config.json` : algunas variables que definen la forma de aplicar la OTA.
