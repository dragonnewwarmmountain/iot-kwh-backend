from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Device, User
from app.deps import get_current_user
from app.services.log_service import log_event

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    location: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None


class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str
    location: Optional[str]
    is_online: bool
    owner_id: int

    class Config:
        from_attributes = True


@router.post("/", response_model=DeviceOut, status_code=201)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="device_id sudah terdaftar")

    device = Device(
        device_id=payload.device_id,
        name=payload.name,
        location=payload.location,
        owner_id=current_user.id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    log_event(db, device_id_str=device.device_id, event_type="device_created", message=f"Device '{device.name}' didaftarkan")
    return device


@router.get("/", response_model=List[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Device).filter(Device.owner_id == current_user.id).all()


@router.get("/{device_id_str}", response_model=DeviceOut)
def get_device(
    device_id_str: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = _get_owned_device(db, device_id_str, current_user)
    return device


@router.patch("/{device_id_str}", response_model=DeviceOut)
def update_device(
    device_id_str: str,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = _get_owned_device(db, device_id_str, current_user)

    if payload.name is not None:
        device.name = payload.name
    if payload.location is not None:
        device.location = payload.location

    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id_str}", status_code=204)
def delete_device(
    device_id_str: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = _get_owned_device(db, device_id_str, current_user)
    db.delete(device)
    db.commit()
    return None


def _get_owned_device(db: Session, device_id_str: str, current_user: User) -> Device:
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bukan device milikmu")
    return device
