from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, index=True, nullable=False)  # cth: "esp32-01"
    name = Column(String(100), nullable=False)
    location = Column(String(100), nullable=True)
    is_online = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="devices")

    sensor_data = relationship("SensorData", back_populates="device", cascade="all, delete-orphan")
    event_logs = relationship("EventLog", back_populates="device", cascade="all, delete-orphan")
    config = relationship("DeviceConfig", back_populates="device", uselist=False, cascade="all, delete-orphan")


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    voltage = Column(Float, nullable=False)     # Volt (dari ZMPT101B)
    current = Column(Float, nullable=False)     # Ampere (dari ACS712)
    power = Column(Float, nullable=False)       # Watt
    energy = Column(Float, nullable=False)      # kWh (akumulasi)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    device = relationship("Device", back_populates="sensor_data")


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)   # "status_change", "command_sent", "sensor_data", "error"
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    device = relationship("Device", back_populates="event_logs")


class DeviceConfig(Base):
    __tablename__ = "device_configs"

    id = Column(Integer, primary_key=True, index=True)
    buzzer_enabled = Column(Boolean, default=True)
    relay_enabled = Column(Boolean, default=False)
    lcd_brightness = Column(Integer, default=100)  # 0-100
    voltage_threshold_low = Column(Float, default=180.0)
    voltage_threshold_high = Column(Float, default=250.0)
    current_threshold = Column(Float, default=10.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, unique=True)
    device = relationship("Device", back_populates="config")