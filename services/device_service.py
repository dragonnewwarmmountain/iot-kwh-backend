from sqlalchemy.orm import Session

from app.database.models import Device, DeviceConfig


def update_device_status(db: Session, device_id_str: str, is_online: bool):
    """Update status online/offline device."""
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        return None

    device.is_online = is_online
    db.commit()
    db.refresh(device)
    return device


def get_device_config(db: Session, device_id_str: str):
    """Ambil konfigurasi device. Kalau belum ada, auto-create default."""
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        return None

    if not device.config:
        config = DeviceConfig(device_id=device.id)
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    return device.config


def update_device_config(db: Session, device_id_str: str, config_data: dict):
    """Update konfigurasi device."""
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        return None

    if not device.config:
        config = DeviceConfig(device_id=device.id, **config_data)
        db.add(config)
    else:
        for key, value in config_data.items():
            if value is not None and hasattr(device.config, key):
                setattr(device.config, key, value)

    db.commit()
    db.refresh(device.config)
    return device.config