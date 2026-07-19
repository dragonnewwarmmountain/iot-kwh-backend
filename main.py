# File: main.py
# Architecture Layer: The Backend Engine
# Purpose: Orchestrates MQTT telemetry, SQLite logging, SSE streaming, and RBAC Authentication.

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import sqlite3
import json
import asyncio
import hashlib
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

# HiveMQ Cloud Configuration
MQTT_BROKER = "6b272dbc7df74a23a319e1c26f5fdd26.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "iot_device"
MQTT_PASS = "Kelompok7_IoT123!"
MQTT_CLIENT_ID = "fastapi_backend_01" 
DEVICE_ID = "esp32-01"

# Topics
TOPIC_TELEMETRY = "sensor/kwh/data"
TOPIC_COMMAND = "actuator/relay/command"
TOPIC_ACTUATOR_COMMAND = "actuator/command"
TOPIC_CONFIG = "actuator/config/threshold"

# Global memory state for SSE
app.state.latest_reading = None 

# --- 2. SQLite Database Initialisation ---
def init_db():
    conn = sqlite3.connect('telemetry.db')
    cursor = conn.cursor()
    
    # Tabel 1: Telemetri Historis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            voltage REAL,
            current REAL,
            power REAL
        )
    ''')
    
    # Tabel 2: Manajemen Pengguna & Peran (RBAC)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT
        )
    ''')

    # Migrasi ringan: menambahkan kolom created_at jika database lama belum memilikinya
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
    except sqlite3.OperationalError:
        pass  # Kolom sudah ada, lewati

    # Mengisi created_at untuk baris lama yang masih kosong (agar tidak NULL)
    cursor.execute(
        "UPDATE users SET created_at = ? WHERE created_at IS NULL",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
    )

    # Seeding Kredensial Administrator Bawaan (Hanya dieksekusi jika tabel kosong)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_admin_pw = hashlib.sha256("admin123".encode()).hexdigest()
        default_user_pw = hashlib.sha256("user123".encode()).hexdigest()
        seed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                       ("admin", default_admin_pw, "admin", seed_time))
        cursor.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                       ("user", default_user_pw, "user", seed_time))
        print("[DATABASE] Tabel pengguna dikonfigurasi. Administrator bawaan disuntikkan.")
        
    conn.commit()
    conn.close()

init_db()

# --- 3. MQTT Broker Integration ---
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    client.subscribe(TOPIC_TELEMETRY)

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        if all(k in data for k in ("voltage", "current", "power")):
            voltage = float(data["voltage"])
            current = float(data["current"])
            power = float(data["power"])
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = sqlite3.connect('telemetry.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (timestamp, voltage, current, power)
                VALUES (?, ?, ?, ?)
            ''', (timestamp_str, voltage, current, power))
            conn.commit()
            conn.close()

            app.state.latest_reading = {
                "timestamp": timestamp_str,
                "voltage": voltage,
                "current": current,
                "power": power
            }
            
            print(f"[MQTT] Data processed: {power} W")
    except Exception as e:
        print(f"[MQTT] Error parsing message: {e}")

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

# --- 4. API Otentikasi (Login & Security) ---
@app.post("/api/v1/auth/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = sqlite3.connect('telemetry.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash, role FROM users WHERE username = ?", (form_data.username,))
    user_record = cursor.fetchone()
    conn.close()
    
    if not user_record:
        raise HTTPException(status_code=401, detail="Nama pengguna tidak terdaftar.")
    
    db_username, db_password_hash, db_role = user_record
    
    # Validasi hash kata sandi (menggunakan SHA-256 untuk kesederhanaan purwarupa IoT)
    provided_pw_hash = hashlib.sha256(form_data.password.encode()).hexdigest()
    if provided_pw_hash != db_password_hash:
        raise HTTPException(status_code=401, detail="Kata sandi tidak valid.")
    
    # Menghasilkan struktur token untuk direspons ke frontend
    return {
        "access_token": f"simulated_jwt_for_{db_username}_role_{db_role}", 
        "token_type": "bearer",
        "role": db_role
    }

# --- 5. API Administrator (Manajemen Pengguna & Analitik) ---
class NewUser(BaseModel):
    username: str
    password: str
    role: str

@app.get("/api/v1/admin/users")
async def get_all_users():
    conn = sqlite3.connect('telemetry.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    users_list = []
    for row in rows:
        user_dict = dict(row)
        # Simulasi status online: anggap admin selalu online
        user_dict['isOnline'] = True if user_dict['username'] == 'admin' else False
        users_list.append(user_dict)
        
    return users_list

@app.post("/api/v1/admin/users")
async def create_new_user(user: NewUser):
    conn = sqlite3.connect('telemetry.db')
    cursor = conn.cursor()
    
    try:
        pw_hash = hashlib.sha256(user.password.encode()).hexdigest()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                       (user.username, pw_hash, user.role, created_at))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username sudah digunakan.")
        
    conn.close()
    return {"status": "success", "message": f"Pengguna {user.username} berhasil diregistrasi."}

@app.delete("/api/v1/admin/users/{username}")
async def delete_user(username: str):
    # Mencegah penghapusan akun administrator utama (proteksi sisi server)
    if username == "admin":
        raise HTTPException(status_code=403, detail="Akun administrator utama tidak dapat dihapus.")

    conn = sqlite3.connect('telemetry.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    existing = cursor.fetchone()

    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")

    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

    return {"status": "success", "message": f"Pengguna {username} berhasil dihapus."}

@app.get("/api/v1/admin/usage")
async def get_energy_analytics():
    conn = sqlite3.connect('telemetry.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Mengambil hanya pengguna non-admin yang masih aktif di database
    # Laporan ini otomatis mengikuti data pengguna riil: akun admin dikecualikan,
    # dan pengguna yang sudah dihapus tidak akan muncul lagi di sini.
    cursor.execute("SELECT username, created_at FROM users WHERE role != 'admin' ORDER BY id ASC")
    active_users = cursor.fetchall()

    usage_list = []
    for row in active_users:
        # Hanya menghitung log telemetri yang tercatat SETELAH pengguna ini dibuat.
        # Dengan begitu, pengguna yang baru saja didaftarkan mulai dari 0 kWh,
        # bukan mewarisi data historis dari sebelum akun mereka ada.
        if row["created_at"]:
            cursor.execute(
                "SELECT COUNT(*) FROM system_logs WHERE timestamp >= ?",
                (row["created_at"],)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM system_logs")
        logs_since_created = cursor.fetchone()[0]

        usage_list.append({
            "username": row["username"],
            "nodes": 1,
            "avgDaily": f"{(logs_since_created * 0.01):.2f} kWh",
            "totalMonthly": f"{(logs_since_created * 0.3):.2f} kWh"
        })

    conn.close()
    return usage_list

# --- 6. API Endpoints (Aktuator & Logs) ---
class ActuatorCommand(BaseModel):
    target: str  
    action: str  

class ThresholdConfig(BaseModel):
    high_threshold: float
    low_threshold: float

@app.post("/api/v2/devices/command")
async def control_actuator_json(command: ActuatorCommand):
    try:
        payload = {"target": command.target.lower(), "action": command.action.upper()}
        mqtt_client.publish(TOPIC_ACTUATOR_COMMAND, json.dumps(payload))
        return {"status": "success", "message": f"Command '{command.action}' dispatched to {command.target}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/devices/config")
async def update_threshold(config: ThresholdConfig):
    try:
        payload = {"high": config.high_threshold, "low": config.low_threshold}
        mqtt_client.publish(TOPIC_CONFIG, json.dumps(payload))
        return {"status": "success", "message": f"Thresholds updated: High={config.high_threshold}W, Low={config.low_threshold}W"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/telemetry/logs")
async def get_historical_logs(limit: int = 20):
    conn = sqlite3.connect('telemetry.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, voltage, current, power FROM system_logs ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- 6.1 System Status (Real MQTT Broker Health Check) ---
@app.get("/api/v1/system/status")
async def get_system_status():
    # Mengecek status koneksi MQTT client secara langsung ke library paho-mqtt,
    # bukan lagi indikator statis di frontend.
    is_connected = mqtt_client.is_connected()
    return {
        "mqtt_connected": is_connected,
        "broker": MQTT_BROKER
    }

# --- 7. Server-Sent Events (SSE) Streaming ---
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
    return EventSourceResponse(sse_generator())