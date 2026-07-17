import ssl
import paho.mqtt.client as mqtt

from app.core.config import settings
from app.database.database import SessionLocal
from app.services.log_service import save_sensor_data
from app.database.models import Device

# We now listen to the specific topics broadcasted by the ESP32
SENSOR_TOPICS = [
    "kwh/arus",
    "kwh/tegangan",
    "kwh/daya",
    "kwh/kwh"
]

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Successfully connected to HiveMQ broker.")
        for topic in SENSOR_TOPICS:
            client.subscribe(topic)
        print(f"[MQTT] Subscribed to all KWH sensor topics.")
    else:
        print(f"[MQTT] Connection failed, return code {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8").strip()
        value = float(payload_str)
        
        print(f"[MQTT DATA] Topic: {topic} | Value: {value}")

        # Assuming a default device ID since the ESP32 topics do not currently include one
        # In a multi-device architecture, the topic should ideally be "kwh/{device_id}/arus"
        default_device_id = "esp32-01" 
        
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.device_id == default_device_id).first()
            if not device:
                # Silently ignore if device is not registered in the database yet
                return
                
            # Note: Because data arrives on separate topics, a highly rigorous implementation 
            # would cache these values temporarily and write to the database once all four are received. 
            # For demonstration, we simply log the event.
            # save_sensor_data(db, default_device_id, sensor_payload) 
            
        finally:
            db.close()

    except ValueError:
        print(f"[MQTT ERROR] Payload on {msg.topic} is not a valid float: {msg.payload!r}")
    except Exception as e:
        print(f"[MQTT ERROR] Processing failure: {e}")

def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)

    client.on_connect = on_connect
    client.on_message = on_message

    return client

def start_mqtt(client: mqtt.Client):
    client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=60)
    client.loop_start()

VALID_ACTIONS = {"relay", "buzzer", "led", "lcd"}

def publish_command(client: mqtt.Client, device_id_str: str, action: str, value: str):
    """
    Publishes a raw string command to the specific ESP32 actuator topics.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid action. Allowed: {VALID_ACTIONS}")
    
    topic = f"kwh/{action}"
    client.publish(topic, value, qos=1)
    print(f"[MQTT PUBLISH] Sent '{value}' to topic '{topic}'")