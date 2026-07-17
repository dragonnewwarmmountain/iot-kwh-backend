from sqlalchemy.orm import Session

from app.database.models import SensorData, EventLog, Device


def save_sensor_data(
    db: Session,
    device_id_str: str,
    voltage: float,
    current: float,
    power: float,
    energy: float,
):
    """Simpan data sensor ke tabel sensor_data. Auto-create device kalau belum ada."""
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        device = Device(
            device_id=device_id_str,
            name=f"Auto-{device_id_str}",
            owner_id=1,  # default owner, sesuaikan di production
        )
        db.add(device)
        db.commit()
        db.refresh(device)

    sensor_data = SensorData(
        device_id=device.id,
        voltage=voltage,
        current=current,
        power=power,
        energy=energy,
    )
    db.add(sensor_data)
    db.commit()
    db.refresh(sensor_data)
    return sensor_data


def log_event(db: Session, device_id_str: str | None, event_type: str, message: str):
    """Catat 1 baris event log. device_id_str boleh None untuk event
    yang tidak terkait device tertentu (mis. login user)."""
    device_pk = None
    if device_id_str:
        device = db.query(Device).filter(Device.device_id == device_id_str).first()
        device_pk = device.id if device else None

    entry = EventLog(
        event_type=event_type,
        message=message,
        device_id=device_pk,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry