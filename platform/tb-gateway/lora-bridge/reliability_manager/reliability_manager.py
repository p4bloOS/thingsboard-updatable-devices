#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import os
import json
import threading
import queue
import time

MQTT_BROKER_HOST = "host.docker.internal"
MQTT_BROKER_PORT = 1884
MQTT_TO_LORA_TOPIC = "thingsboard/OMG_ESP32_LORA/commands/MQTTtoLORA"
MAX_RETRIES = 4
ACK_MAX_COUNT = 100

# Environment variables
username = os.getenv('mqtt_user')
password = os.getenv('mqtt_password')
id_list = os.getenv('device_id_list').split(',')
print(f"IDs de los dispositivos a manejar: {id_list}")

estimated_rtt_time = 5 # (segundos) Este valor  puede ir reduciéndose si se detectan ACKs que tardan menos en volver
retry_timeout = estimated_rtt_time * 2

to_lora_queue = queue.Queue()
mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
expected_ack_count = 0
ack_received_event = threading.Event()


# Callback para el establecimiento de la conexión (se recibe CONNACK desde el servidor)
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Suscripciones
    for device_id in id_list:
        client.subscribe(f"thingsboard/OMG_ESP32_LORA/LORAtoMQTT/{device_id}/reliable/#")
        client.subscribe(f"thingsboard/OMG_ESP32_LORA/LORAtoMQTT/{device_id}/ack")
        client.subscribe(f"thingsboard/OMG_ESP32_LORA/commands/MQTTtoLORA/reliable/{device_id}")


# Recepción de mensajes
def on_message(client, userdata, msg):

    print(f">>>> {msg.topic} | {msg.payload}")
    try:
        message_data = json.loads(msg.payload.decode('utf-8'))
    except Exception as e:
        print(f"Error al descodificar el mensaje recibido como JSON: {e}")
        return

    topic_parts = msg.topic.split('/')

    # Mensaje desde LoRa (devolveremos ACK)
    if topic_parts[2] == "LORAtoMQTT" and topic_parts[4] == "reliable":
        device_id = topic_parts[3]
        print(f"Mensaje para confirmar proveniente del dispositivo {device_id}")
        ack_count = message_data.get("count")
        if ack_count == None:
            print('ERROR: El JSON recibido no contiene un campo "count"')
        ack_msg = '{"message":"{' + \
            f'\\"id\\":\\"{device_id}\\",\\"ack\\":{ack_count}'  + \
            '}"}'
        print("Enviando ACK")
        client.publish(MQTT_TO_LORA_TOPIC, ack_msg.encode('utf-8'), qos=2)

    # ACK desde LoRa recibido
    elif topic_parts[2] == "LORAtoMQTT" and topic_parts[4] == "ack":
        if message_data.get("msg", {}).get("count") == expected_ack_count:
            ack_received_event.set()

    # Mensaje hacia LoRa (activamos rutina de reenvío hasta recibir ACK)
    elif topic_parts[3] == "MQTTtoLORA":
        device_id = topic_parts[5]
        to_lora_queue.put((device_id, message_data))


def reliable_delivery():
    global expected_ack_count
    global estimated_rtt_time
    global retry_timeout
    while True:
        device_id, msg_data = to_lora_queue.get()
        msg_data["id"] = device_id
        msg_data["requires_ack"] = expected_ack_count
        msg_data_json = json.dumps(msg_data, separators=(',', ':'))
        msg_data_json_formatted = msg_data_json.replace('"', '\\"')
        msg_to_send = '{"message":"' + msg_data_json_formatted + '"}'
        print(f"Realizando envío fiable hacia LoRa del mensaje: {msg_to_send}")
        success = False
        start_time = time.time()
        for tries in range(MAX_RETRIES):
            mqttc.publish(MQTT_TO_LORA_TOPIC, msg_to_send.encode('utf-8'))
            if ack_received_event.wait(timeout=retry_timeout):
                elapsed_time = time.time() - start_time
                if elapsed_time < estimated_rtt_time:
                    estimated_rtt_time = elapsed_time
                    retry_timeout = estimated_rtt_time * 2
                    print(f"Reajustado el tiempo RTT estimado: {estimated_rtt_time}s "
                        f"(retry_timeout={retry_timeout})")
                success = True
                ack_received_event.clear()
                break
        if not success:
            print("ERROR: Número máximo de reenvíos alcanzado. Descartando mensaje")
        expected_ack_count = (expected_ack_count + 1) % ACK_MAX_COUNT


mqttc.on_connect = on_connect
mqttc.on_message = on_message

threading.Thread(target=reliable_delivery, daemon=True).start()

# Autenticación y conexión
mqttc.username_pw_set(username, password)
mqttc.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

mqttc.loop_forever()
