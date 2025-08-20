### Gateway de Thingsboard personalizado (conecta dispositivos BLE y LoRa)

El gateway disponible en este proyecto se trata de uno personalizado para permitir el intercambio del
paquete OTA, a través de un conector BLE y un conector MQTT que indirectamente se se comunicará con un
dispositivo LoRa, sin olvidar el correcto intercambio de datos en forma de atributos y telemetría.

**1. Despligue del Gateway conectado al servidor**

En primer lugar, hemos de crear el Gateway en Thingsboard, desde la sección *Entidades/Gateways*,
que podemos llamar *Updatable-devices-gateway*.
Una vez creado, consultaremos su *Access token*, copiaremos su valor y lo pondremos en la variable
de entorno *accessToken* defininida dentro del archivo [docker-compose.yml](docker-compose.yml) (services>tb-gateway>environment>accessToken).

A continuación ya podemos lanzar el contenedor docker:
```bash
cd platform/tb-gateway
docker compose up -d
```

Comandos útiles:
```bash
docker compose logs -f tb-gateway     # Consultar los logs
docker compose stop tb-gateway        # Detener el contenedor
docker compose start tb-gateway       # Reanudar el contenedor
```

**2. Configuración del conector BLE**

En Thingsboard, dentro del Gateway recién creado, añadiremos un nuevo conector BLE llamado (necesariamente) *My-BLE-Connector*.
Para su configuración emplearemos el fichero [BLE-connector-config.json](BLE-connector-config.json), que está diseñado para cumplir con los requisitos de la aplicación de ejemplo.
En ese fichero se define, principalmente, la asociación entre elementos de Thingsboard, tales como atributos o
métodos RPC, y las caracterísiticas de BLE que emplea el dispositivo. Cambiaremos la MAC de dicha configuración
para adaptarla al dispositivo en cuestión.




**X. Descripción del Gateway **

Este gateway extiende la funcionalidad del gateway estándar de Thingsboard, haciendo uso del volumen
tb-gw-extensions, donde hemos añadido estos archivos desarrollados:

- [tb-gw-extensions/ble/utf8_bytes_ble_uplink_converter.py](
gateway/tb-gw-extensions/ble/utf8_bytes_ble_uplink_converter.py) :
Implementa un nuevo converter de tipo uplink, para poder recibir valores de atributos y telemetría codificados en UTF-8.
