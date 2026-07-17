from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Device, User
from app.schemas.sensor import DeviceCommand
from app.deps import get_current_user  # ASUMSI nama dependency, sesuaikan kalau beda
from app.mqtt.client import publish_command, VALID_ACTIONS
from app.services.log_service import log_event

router = APIRouter(prefix="/controls", tags=["controls"])

VALID_ONOFF_ACTIONS = {"relay", "buzzer", "led"}


@router.post("/{device_id_str}/command")
def send_device_command(
    device_id_str: str,
    command: DeviceCommand,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.device_id == device_id_str).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")

    if device.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bukan device milikmu")

    if command.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"action harus salah satu dari {sorted(VALID_ACTIONS)}",
        )

    # Validasi value: ON/OFF untuk relay,buzzer,led; bebas (tapi dibatasi
    # panjang) untuk lcd -- sesuai apa yang firmware terima di mqttCallback()
    if command.action in VALID_ONOFF_ACTIONS:
        if command.value.upper() not in {"ON", "OFF"}:
            raise HTTPException(
                status_code=400,
                detail=f"value untuk action '{command.action}' harus 'ON' atau 'OFF'",
            )
        value_to_send = command.value.upper()
    else:  # action == "lcd"
        if len(command.value) > 32:
            raise HTTPException(status_code=400, detail="value lcd maksimal 32 karakter")
        value_to_send = command.value

    # ASUMSI: mqtt client disimpan di app.state.mqtt_client saat startup
    # (lihat main.py / app startup event). Sesuaikan kalau nama/lokasinya beda.
    mqtt_client = getattr(request.app.state, "mqtt_client", None)
    if mqtt_client is None:
        raise HTTPException(status_code=503, detail="MQTT client belum siap")

    try:
        publish_command(mqtt_client, device_id_str, command.action, value_to_send)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_event(
        device_id_str=device_id_str,
        event_type="command_sent",
        message=f"Command '{command.action}'='{value_to_send}' dikirim oleh {current_user.username}",
    )

    return {
        "status": "sent",
        "device_id": device_id_str,
        "action": command.action,
        "value": value_to_send,
    }