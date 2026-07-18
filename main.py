# File: main.py
# Architecture Layer: The Backend Engine
# Purpose: Orchestrates MQTT telemetry, SQLite logging, and SSE streaming to the frontend.

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import sqlite3
import json
import asyncio
from datetime import datetime

# --- 1. Core Configuration ---
app = FastAPI(title="IoT Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HiveMQ Cloud Configuration (Injected Credentials)
MQTT_BROKER = "6b272dbc7df74a23a319e1c26f5fdd26.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "iot_device"
MQTT_PASS = "Kelompok7_IoT123!"
MQTT_CLIENT_ID = "fastapi_backend_01" 
DEVICE_ID = "esp32-01"

# Legacy Topics
TOPIC_TELEMETRY = "sensor/kwh/data"
TOPIC_COMMAND = "actuator/relay/command"

# New Advanced Topics
TOPIC_ACTUATOR_COMMAND = "actuator/command"
TOPIC_CONFIG = "actuator/config/threshold"

# Global memory state to hold the latest reading for SSE transmission
# We attach this directly to the app state so it is accessible across threads
app.state.latest_reading = None 

# --- 2. SQLite Database Initialisation ---
def init_db():
    conn = sqlite3.connect('telemetry.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            voltage REAL,
            current REAL,
            power REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 3. MQTT Broker Integration ---
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe(TOPIC_TELEMETRY)
    print(f"[MQTT] Subscribed to telemetry topic: {TOPIC_TELEMETRY}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        if all(k in data for k in ("voltage", "current", "power")):
            voltage = float(data["voltage"])
            current = float(data["current"])
            power = float(data["power"])
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 1. Log to SQLite
            conn = sqlite3.connect('telemetry.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (timestamp, voltage, current, power)
                VALUES (?, ?, ?, ?)
            ''', (timestamp_str, voltage, current, power))
            conn.commit()
            conn.close()

            # 2. Push to the asynchronous state for SSE broadcasting
            broadcast_data = {
                "timestamp": timestamp_str,
                "voltage": voltage,
                "current": current,
                "power": power
            }
            app.state.latest_reading = broadcast_data 
            
            print(f"[MQTT] Data processed: {power} W")
    except Exception as e:
        print(f"[MQTT] Error parsing message: {e}")

# Initialize MQTT Client with TLS for HiveMQ
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.tls_set() 
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

try:
    print(f"[MQTT] Attempting connection to {MQTT_BROKER}...")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start() 
except Exception as e:
    print(f"[MQTT] Connection failed: {e}")

# --- 4. API Endpoints (Legacy) ---
class RelayCommand(BaseModel):
    action: str
    value: str

class DeviceRequest(BaseModel):
    device_id: str
    command: RelayCommand

@app.post("/api/v1/devices/command")
async def send_actuator_command(request: DeviceRequest):
    if request.command.action == "relay" and request.device_id == DEVICE_ID:
        command_state = request.command.value.upper()
        if command_state in ["ON", "OFF"]:
            mqtt_client.publish(TOPIC_COMMAND, command_state)
            return {"status": "success", "message": f"Relay command '{command_state}' published."}
        
    raise HTTPException(status_code=400, detail="Invalid command or device ID.")

@app.get("/api/v1/telemetry/logs")
async def get_historical_logs(limit: int = 20):
    conn = sqlite3.connect('telemetry.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT timestamp, voltage, current, power 
        FROM system_logs 
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# --- 5. Server-Sent Events (SSE) Streaming ---
async def sse_generator():
    last_sent_data = None
    while True:
        if hasattr(app.state, 'latest_reading') and app.state.latest_reading:
            current_reading = app.state.latest_reading
            if current_reading != last_sent_data:
                yield f"data: {json.dumps(current_reading)}\n\n"
                last_sent_data = current_reading
        
        await asyncio.sleep(0.5) 

@app.get("/api/v1/telemetry/stream")
async def telemetry_stream(request: Request):
    print("[SSE] Client connected to live telemetry stream.")
    return EventSourceResponse(sse_generator())

# --- 6. API Endpoints (New Advanced Architecture) ---
class ActuatorCommand(BaseModel):
    target: str  # e.g., "led" or "buzzer"
    action: str  # e.g., "ON" or "OFF"

class ThresholdConfig(BaseModel):
    high_threshold: float
    low_threshold: float

@app.post("/api/v2/devices/command")
async def control_actuator_json(command: ActuatorCommand):
    try:
        # Construct the JSON payload for the ESP32
        payload = {
            "target": command.target.lower(),
            "action": command.action.upper()
        }
        
        # Publish to the new command topic
        mqtt_client.publish(TOPIC_ACTUATOR_COMMAND, json.dumps(payload))
        
        return {
            "status": "success", 
            "message": f"Command '{command.action}' dispatched to {command.target}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/devices/config")
async def update_threshold(config: ThresholdConfig):
    try:
        # Construct the JSON payload matching the C++ firmware expectations
        payload = {
            "high": config.high_threshold,
            "low": config.low_threshold
        }
        
        # Publish to the dedicated configuration topic
        mqtt_client.publish(TOPIC_CONFIG, json.dumps(payload))
        
        return {
            "status": "success", 
            "message": f"Thresholds updated: High={config.high_threshold}W, Low={config.low_threshold}W"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))