# IoT KWH Meter Telemetry System

**Kelompok 7 | Information Systems, ITPLN**

---

## Link Penting

| Komponen | Link/Info |
|---|---|
| **Repository Backend (GitHub)** | https://github.com/dragonnewwarmmountain/iot-kwh-backend |
| **Dashboard Web (Live)** | https://kwhmeter.nfy.fyi/dashboard/login.php |
| **Firmware ESP32** | Ada di dalam file `.zip` pada repo backend ini (lihat langkah 6) |

---

## Arsitektur Singkat

```
ESP32 (sensor) → MQTT (HiveMQ Cloud) → Backend FastAPI (lokal + ngrok) → SQLite
                                                    ↓
                                          Frontend PHP (InfinityFree, sudah online)
```

- **Frontend** sudah online 24/7 di hosting InfinityFree — tidak perlu di-setup lagi.
- **Backend** perlu dijalankan secara manual di komputer/laptop, lalu di-tunnel ke internet lewat **ngrok** supaya frontend yang online bisa mengaksesnya.
- **ESP32** perlu diflash dengan firmware yang tersedia di repo ini agar bisa mengirim data sensor & menerima perintah aktuator.

---

## Yang Dibutuhkan Sebelum Mulai

- [Python 3.10+](https://www.python.org/downloads/) dan `pip`
- [ngrok](https://ngrok.com/download) (akun gratis sudah cukup)
- [Arduino IDE](https://www.arduino.cc/en/software) (untuk flash firmware ke ESP32)
- Board ESP32 + sensor (ACS712, ZMPT101B), LCD 16x2 I2C, buzzer, LED
- Koneksi WiFi untuk ESP32

---

## Cara Menjalankan Aplikasi

### 1. Clone Repository Backend

```bash
git clone https://github.com/dragonnewwarmmountain/iot-kwh-backend.git
cd iot-kwh-backend
```

### 2. Install Dependency Python

```bash
pip install fastapi uvicorn paho-mqtt sse-starlette
```

### 3. Jalankan Backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Biarkan terminal ini tetap terbuka — backend harus terus berjalan selama sistem digunakan. Saat pertama kali dijalankan, database `telemetry.db` beserta akun default akan otomatis dibuat.

### 4. Buka Tunnel dengan Ngrok

Buka **terminal baru** (jangan tutup terminal backend), lalu jalankan:

```bash
ngrok http 8000
```

Ngrok akan menampilkan URL publik, contohnya:

```
Forwarding    https://xxxx-xxxx-xxxx.ngrok-free.dev -> http://localhost:8000
```

**Catat URL ini** — akan dipakai di langkah berikutnya.

> **Penting:** Setiap kali ngrok dijalankan ulang (restart), URL publiknya akan **berubah**. Kalau ini terjadi, lanjut ke langkah 5 untuk memperbarui URL di frontend.

### 5. Perbarui URL Backend di Frontend (jika URL ngrok berubah)

Frontend yang sudah online di InfinityFree perlu tahu URL ngrok terbaru. Buka dua file berikut di file manager hosting kamu:

- `assets/js/api.js`
- `assets/js/admin.js`

Cari baris:

```javascript
const API_BASE_URL = 'https://xxxx-xxxx-xxxx.ngrok-free.dev';
```

Ganti dengan URL ngrok yang baru dari langkah 4, lalu simpan.

### 6. Flash Firmware ke ESP32

1. Di dalam repo backend yang sudah kamu download/clone, cari file **`.zip`** yang berisi kode firmware ESP32, lalu **ekstrak** file zip tersebut.
2. Buka file `.ino` hasil ekstrak menggunakan Arduino IDE.
3. Install library yang dibutuhkan lewat Library Manager: `PubSubClient`, `ArduinoJson`, `ACS712`, `ZMPT101B`, `LiquidCrystal_I2C`.
4. Sesuaikan kredensial WiFi di bagian atas kode:
   ```cpp
   const char* ssid     = "NAMA_WIFI_KAMU";
   const char* password = "PASSWORD_WIFI_KAMU";
   ```
5. Sambungkan ESP32 ke komputer via USB, pilih board & port yang sesuai di Arduino IDE.
6. Klik **Upload**.
7. Buka **Serial Monitor** (baudrate `115200`) untuk memastikan ESP32 berhasil konek ke WiFi dan MQTT broker.

### 7. Buka Dashboard Web

Akses dashboard di:

```
https://kwhmeter.nfy.fyi/dashboard/login.php
```

**Akun default:**

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| User | `vinandme` | `177013` |

---

## Ringkasan Urutan Menjalankan Sistem

```
1. Jalankan backend (uvicorn)
        ↓
2. Jalankan ngrok, catat URL barunya
        ↓
3. (Jika URL berubah) update api.js & admin.js di hosting frontend
        ↓
4. Nyalakan ESP32 (pastikan firmware sudah diflash & WiFi tersambung)
        ↓
5. Buka dashboard web → login → sistem siap digunakan
```

---

## Troubleshooting Singkat

| Masalah | Kemungkinan Penyebab |
|---|---|
| "Broker Offline" di dashboard | Backend belum dijalankan, atau ESP32 belum konek ke MQTT |
| Data sensor tidak muncul | ESP32 belum menyala / belum tersambung WiFi |
| Login gagal terus | Backend belum jalan, atau URL ngrok di `api.js`/`auth.js` sudah kedaluwarsa (lihat langkah 5) |
| Perubahan kode tidak muncul di browser | Cache browser — coba hard refresh (`Ctrl+Shift+R`) |

---


