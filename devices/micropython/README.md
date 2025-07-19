## Dispositivo Micropython actualizable a través de Thingsboard

### Descripción del sistema

Este es un sistema desarrollado para ser instalado como el firmware de un dispositivo con Micropython, con la finalidad de habilitar en dicho dispositivo la actualización OTA a través de la plataforma Thingsboard. El sistema se divide en 2 componentes:

- **Biblioteca *ota-helper*** (paquete mip en [mip_packages/ota-helper-lib.json](mip_packages/ota-helper-lib.json))

    Su paquete mip instala el módulo [**ota_helper.py**](src/lib/ota_helper.py) junto con sus dependencias. Este módulo define 2 clases principales:
    - `UpdatableTBMqttClient`: Clase derivada de `TBDeviceMqttClient` perteneciente al [thingsboard-micropython-client-sdk](https://github.com/p4bloOS/thingsboard-micropython-client-sdk), para perfilar la comunicación con Thingsboard relativa a la actualización OTA y tener cuenta nuestro método propio para la instalación del paquete OTA recibido. Lo particular de este cliente, a grandes rasgos, es que, cuando ha terminado la transferencia del nuevo firmware, lo guarda en un archivo y reinicia el dispositivo, esperando que dicho paquete se instale en la rutina de inicio.
    - `OTAInstaller`: Clase dedicada a la instalación de un paquete OTA recibido, con métodos para comprobar el correcto formato del archivo, su coherencia con los datos reportados por la plataforma y su instalación sobre el sistema de ficheros con diferentes parámetros de personalización. Está pensada para ser usada en la rutina de inicio del dispositivo, tras comprobar que existe un nuevo paquete OTA listo para instalarse.
    Esta clase ha sido en parte inspirada por el proyecto [uota](https://github.com/mkomon/uota) del usuario [mkomon](https://github.com/mkomon).

      > Estas clases asumen para en su funcionamiento la existencia de un archivo en la raíz del dispositivo llamado `FW_METADATA.json`, que sirve para determinar el título y versión del firmware instalado actualmente.


- **Programa de ejemplo** (paquete mip en [mip_packages/example-program.json](mip_packages/example-program.json))

    Este componente está conformado por los siguientes scripts y archivos de configuración (con sus rutas tal como se verían en el dispositivo una vez instalados):
    - [`/boot.py`](src/boot.py): Script de incio que establece la conexión de red, instala el paquete OTA si hay uno nuevo disponible y comunica a Thingsboard el resultado.
    - [`/main.py`](src/main.py): Script principal que realiza varias tareas en paralelo mediante [asyncio](https://docs.micropython.org/en/latest/library/asyncio.html) mientras mantiene una escucha periódica de los mensajes de Thingsboard.
    - [`/FW_METADATA.json`](src/FW_METADATA.json): Fichero en la raíz del dispositivo que indica el título y la versión actual del firmware. (necesario para que la bilioteca ota-helper funcione)
    - [`/lib/utils.py`](src/lib/utils.py): Biblioteca de utilidades de la cual se sirven *boot.py* y *main.py*. Ayuda a gestionar la conexión a la red, la lectura de los archivos de configuración, el logging (mediante la biblioteca [logging](https://github.com/micropython/micropython-lib/blob/master/python-stdlib/logging/logging.py)) y la creación de un *UpdatableTBMqttClient* configurado en base a los ficheros de configuración.
    - [`/config/network_config.json`](config/network_config.json): Contiene atributos para establecer conexión con la red.
    - [`/config/ota_config.json`](config/ota_config.json): Contiene atributos para configurar la actualización OTA.
    - [`/config/thingsboard_config.json`](config/thingsboard_config.json): Contiene atributos para configurar la conexión con Thingsboard.


---

### Instalación

*Como requisito necesitaremos una placa de desarrollo con Micropython instalado.*

Una vez clonado este repositorio, crear un entorno virtual de Python:
```bash
# (En el entorno de desarrollo)
cd thingsboard-updatable-devices/
python3 -m venv venv
```

Configurar el **venv** para ayudar al LSP de nuestro IDE a captar las referencias:
```bash
site_packages_dir="$(./venv/bin/python -c "import site; print(site.getsitepackages()[0])")"
realpath devices/micropython/src/external/tb-client-sdk/ \
> "${site_packages_dir}/tb-client-lib.pth"
realpath devices/micropython/src/lib/ > "${site_packages_dir}/my-lib.pth"
./venv/bin/pip install micropython-esp32-stubs==1.24.1.post2
```

Entrar al **venv** e instalar [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) para controlar el dispositivo mediante USB:
```bash
source venv/bin/activate
pip install mpremote
```

Borrar todo todos los ficheros existentes en el dispositivo:
```bash
mpremote rm -rv :/
```

**Paquete mip *ota-helper-lib***

Contiene la biblioteca ota_helper.py y sus dependencias.
```bash
# Instalación desde el contenido clonado
cd devices/micropython/mip_packages
mpremote mip install ota-helper-lib.json
```

**Paquete mip *example-program***

Contiene los scripts que conforman un programa de ejemplo que realiza una actualización, junto con los archivos de configuración que usan dichos scripts.
```bash
cd devices/micropython/mip_packages
mpremote mip --target "" install example-program.json
```

---

### Configuración

La aplicación de ejemplo usa una serie de ficheros de configuración sin los cuales no puede funcionar:

- `network_config.json` : El dispositivo intentará conectarse a la red wifi cuyas credenciales se configuran en este fichero. Atributos esperados:
    - SSID
    - password

- `thingsboard_config.json` : Define las características de la conexión con la plataforma Thingsboard. Atributos esperados:
    - server_host
    - server_port
    - device_access_token (*access token* de la entidad dispositivo creada previamente en Thingsboard)
    - check_msg_period_ms (en el programa principal, tiempo de espera en el bucle de comprobación de nuevos mensajes recibidos desde Thingsboard, en milisegundos)

- `ota_config.json` : Algunas variables que definen la forma de aplicar la OTA. Atributos esperados:
    - chunk_size (tamaño de chunk en la transferencia del firmware: número de bytes a transmitir en cada mensaje o "" para transmitir todo en un solo mensaje)
    - tmp_filename (nombre del fichero temporal donde se almacenará el firmware recibido antes de ser instalado)
    - excluded_files (lista de rutas que no serán borradas ni modificadas en ningún punto del proceso)
    - clear_filesystem (indica si realizará un borrado del sistema de archivos antes de instalar el nuevo firmware)

Se pueden tomar como ejemplo los archivos del directorio [config/](config/).

Podemos editar estos ficheros en base las características de nuestro sistema e instalarlos junto con el paquete mip **example-program**, o instalarlos por separado con un comando así:
```bash
mpremote mkdir config
mpremote cp -r devices/micropython/config :config
```

---

### Generación de paquetes OTA

En el directorio `devices/micropython/tools` se puede encontrar el script el sript [gen_ota_package.py](tools/gen_ota_package.py):


```bash
./gen_ota_package.py --help
# >> Salida esperada:
#
# usage: gen_ota_package.py [-h] [-n NAME]
#
# Genera, en el directorio tools/generated, un paquete OTA para MicroPython a partir del estado actual del dispositivo conectado con mpremote.
#
# options:
#   -h, --help       show this help message and exit
#   -n, --name NAME  Nombre del archivo de salida (por defecto se forma a partir de la info. encontrada en src/FW_METADATA.json)
```

Ejemplo de uso:

```bash
cd devices/micropython/tools

# Instalamos este proyecto en el dispositivo Micropython conectado
mpremote rm -rv :/
./install.sh

# Generamos el paquete OTA a partir del estado actual del dispositivo
./gen_ota_package.py
# >> Salida esperada:
# Copiando sistema de ficheros del dispositivo a un directorio temporal
# cp :/ /tmp/tmpk8cpl92s
# Creando archivo comprimido TAR GZ
# Archivo de salida creado: .../devices/micropython/tools/generated/micropython-OTA-client_v0.tar.gz
```
