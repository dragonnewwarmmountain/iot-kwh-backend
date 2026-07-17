from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Device, SensorData, User
from app.schemas.sensor import SensorDataOut
from app.deps import get_current_user

router = APIRouter(prefix="/sensors", tags=["sensors"])

@router.get("/{device_id_str}", response_model=List[SensorDataOut])
def get_sensor_history(
    device_id_str: str,
    start: Optional[datetime] = Query(None, description="Filter dari tanggal (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="Filter sampai tanggal (ISO 8601)"),
    limit: int = Query(100, le=1000, description="Maks jumlah row, default 100"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")

    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bukan device milikmu")

    query = db.query(SensorData).filter(SensorData.device_id == device.id)

    if start:
        query = query.filter(SensorData.recorded_at >= start)
    if end:
        query = query.filter(SensorData.recorded_at <= end)

    results = query.order_by(SensorData.recorded_at.desc()).limit(limit).all()
    return results

@router.get("/{device_id_str}/latest", response_model=SensorDataOut)
def get_latest_sensor_data(
    device_id_str: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")

    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bukan device milikmu")

    latest = (
        db.query(SensorData)
        .filter(SensorData.device_id == device.id)
        .order_by(SensorData.recorded_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="Belum ada data sensor untuk device ini")

    return latest