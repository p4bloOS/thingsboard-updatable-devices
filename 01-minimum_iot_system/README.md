## Arranque de la plataforma

Como requisito, necesitas tener instalado docker.

Accede al directorio platform:
```
cd TFG/01-minimum_io_system/plataform
```

Puedes levantar el contenedor por primera vez con:
```
docker compose up -d
```

Si ha iniciado correctamente, deberías poder acceder al cliente web a través de: http://localhost:8080/

Consultar los logs:
```
docker compose logs -f mytb
```

Detener/reanudar el contenedor:
```
docker compose stop mytb
docker compose start mytb
```

Estas son las credenciales predeterminadas con las que puedes ingresar al cliente web:
- System Administrator: sysadmin@thingsboard.org / sysadmin
- Tenant Administrator: tenant@thingsboard.org / tenant
- Customer User: customer@thingsboard.org / customer

---

## Despliegue del dispositivo

### 1. Instalación de micropython en la ESP-32

Puedes encontrar información más completa en:
https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro

1.1. Mediante un entorno virtual de python instalamos las dependencias que necesitamos:

```
cd TFG/
python3 -m venv py_venv
source py_venv/bin/activate
pip install esptool
```

1.2. Conectamos la placa a nuestro ordenador por USB.
En nuestro caso, el puerto serie correspondiente nos aparece en el archivo /dev/ttyUSBO.

1.3. Limpiamos la memoria flash y grabamos el archivo de firmware **ESP32_GENERIC-20241129-v1.24.1.bin**, el cual hemos obtenido de la página oficial de micropython (https://micropython.org/download/?port=esp32)
```
esptool.py erase_flash
esptool.py --baud 460800 write_flash 0x1000 <ESP32_GENERIC-20241129-v1.24.1.bin>
```

### 2. Instalación de nuestro programa python

2.1. Instala la herramienta mpremote y comprueba su funcionamiento (el comportamiento por defecto es abrir una REPL):
```
$ pip install mpremote
$ mpremote
Connected to MicroPython at /dev/ttyUSB0
Use Ctrl-] or Ctrl-x to exit this shell

>>> print("hello world")
hello world
```

2.2. Instala la biblioteca umqtt.simple para que nuestro programa pueda funcionar:
```
mpremote mip install umqtt.simple
```

2.3. Instala el programa en la placa:
```
cd TFG/01-minimum_iot_system/devices/simple-micropython-mqtt-client
mpremote fs cp main.py :main.py
```
