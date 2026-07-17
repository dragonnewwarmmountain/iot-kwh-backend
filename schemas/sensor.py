from datetime import datetime
from pydantic import BaseModel

class SensorDataOut(BaseModel):
    id: int
    voltage: float
    current: float
    power: float
    energy: float
    recorded_at: datetime
    device_id: int

    class Config:
        from_attributes = True

class DeviceCommand(BaseModel):
    action: str
    value: str