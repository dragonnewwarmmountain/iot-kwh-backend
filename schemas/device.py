from datetime import datetime
from pydantic import BaseModel


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    location: str | None = None


class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str
    location: str | None
    is_online: bool
    created_at: datetime

    class Config:
        from_attributes = True