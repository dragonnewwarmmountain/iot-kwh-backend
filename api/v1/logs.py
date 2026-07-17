from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Device, EventLog, User
from app.deps import get_current_user

router = APIRouter(prefix="/logs", tags=["logs"])


class EventLogOut(BaseModel):
    id: int
    event_type: str
    message: str
    created_at: datetime
    device_id: Optional[int]

    class Config:
        from_attributes = True


@router.get("/{device_id_str}", response_model=List[EventLogOut])
def get_device_logs(
    device_id_str: str,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bukan device milikmu")

    logs = (
        db.query(EventLog)
        .filter(EventLog.device_id == device.id)
        .order_by(EventLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs