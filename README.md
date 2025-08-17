# thingsboard-updatable-devices

Este es un proyecto que pretende implementar la actualización OTA en dispositivos IoT para la plataforma Thingsboard, concretamente en 2 clases de dispositvos:
- Microcontrolador con Micropython
- Mini-PC con Linux (Buildroot)

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
- [ ] 07-final_revision


## Características relevantes

### Para **Micropython**:

- Biblioteca **thingsboard-ota-helper**, capaz de gestionar la comunicación con Thingsboard relativa a las actualizaciones OTA y aplicar un paquete OTA sobre el sistema de ficheros de micropython.
- Aplicación de ejemplo para un dispositivo cliente de Thingsboard, actualizable y capaz de realizar otras tareas concurrentemente.
- Paquetes [mip](https://docs.micropython.org/en/latest/reference/packages.html) relativos a las 2 características anteriores. Véase el directorio [devices/micropython/mip_packages](devices/micropython/mip_packages).
- Herramienta [gen_ota_package.py](devices/micropython/tools/gen_ota_package.py) para generar paquetes de actualización OTA en formato **tar.gz**.


### Para **Linux embebido** (*POR IMPLEMENTAR*):

- Adaptación a Python estándar sobre Linux de la biblioteca thingsboard-ota-helper y el programa de ejemplo.
- Imagen personalizada de Linux creada con [Buildroot](https://buildroot.org/), que contiene un servicio para comunicarse con Thingsboard y aplicar las actualizaciones mediante [RAUC](https://rauc.io/)
- Posibles herramientas por definir.

### Conectividad:

- Este proyecto funciona por defecto cuando el dispositivo se conecta directamente por **MQTT** a la plataforma o a alguno de sus gateways.
- Soporte para **BLE**: *POR IMPLEMENTAR*
- Soporte para **LoRa**: *POR IMPLEMENTAR*


## Documentación del proyecto

- Plataforma **Thingsboard** aplicada a una flota actualizable: [platform/README.md](platform/README.md)
- Dispositivo **Micropython** actualizable a través de Thingsboard: [devices/micropython/README.md](devices/micropython/README.md)
- Dispositivo **Linux** actualizable a través de Thingsboard: [devices/linux/README.md](devices/linux/README.md)

---

Este respositorio contiene un submódulo, cosa que deberemos tener en cuenta el clonarlo:
```bash
git clone https://github.com/p4bloOS/thingsboard-updatable-devices.git
cd thingsboard-updatable-devices/
git submodule update --init --recursive
```

El repositorio que se incluye como un submódulo en [devices/micropython/src/external/tb-client-sdk/](devices/micropython/src/external/tb-client-sdk/) es un fork de la biblioteca [thingsboard-micropython-client-sdk](https://github.com/thingsboard/thingsboard-micropython-client-sdk), que ha sido modificada para la corrección de un bug encontrado y la reducción del logging excesivo.

Enlace al fork: [https://github.com/p4bloOS/thingsboard-micropython-client-sdk](https://github.com/p4bloOS/thingsboard-micropython-client-sdk)
