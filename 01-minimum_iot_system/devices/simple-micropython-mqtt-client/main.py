import time

from umqtt.simple import MQTTClient

#NETWORK_NAME = 'DIGIFIBRA-QFzA'
#NETWORK_PASSWORD = 'cFCE45CtEGkY'
NETWORK_NAME = 'MOVISTAR_9CA0'
NETWORK_PASSWORD = '7u34A7v4Ju4A4Wx7A977'

def do_connect():
    import network
    wlan = network.WLAN(network.WLAN.IF_STA)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to# network...')
        wlan.connect(NETWORK_NAME, NETWORK_PASSWORD)
        while not wlan.isconnected():
            print("Esperando a la conexión wifi...")
            time.sleep(1)
    print('Configuración de red:', wlan.ipconfig('addr4'))

do_connect()
mqttClient = MQTTClient(client_id="umqtt_client", server="192.168.1.50", port="1883", user="YmU1QlMwHPJ7ubTB1mHL", password="")
mqttClient.connect()
mqttClient.publish(b"v1/devices/me/telemetry", b"""{"temperature":245}""")
#    ^
#    |
#    *-- equivalente a: mosquitto_pub -d -q 1 -h "YOUR_TB_HOST" -p "1883" \
#        -t "v1/devices/me/telemetry" -u "YOUR_ACCESS_TOKEN" -m {"temperature":245}
