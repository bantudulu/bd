from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Notifikasi, Pesanan
from app.models_push import PushDevice

router = APIRouter(prefix="/api/notifikasi", tags=["notifications"])


def require_customer(request: Request) -> dict:
    user = request.state.user
    if not user or user.get("role") != "CUSTOMER":
        raise HTTPException(status_code=401 if not user else 403, detail="Akses ditolak.")
    return user


class DeviceRegistration(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    platform: str = Field(default="android", min_length=3, max_length=20)


def notification_payload(n: Notifikasi, order: Pesanan | None = None) -> dict:
    return {
        "id": n.id,
        "judul": n.judul,
        "pesan": n.pesan,
        "dibaca": n.dibaca,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "pesanan_id": n.pesanan_id,
        "kode_pesanan": order.kode if order else None,
        "action_url": f"/pesanan/{order.kode}" if order else None,
    }


@router.get("")
async def list_notifications(request: Request, limit: int = 50, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    limit = max(1, min(limit, 100))
    result = await db.execute(
        select(Notifikasi)
        .where(Notifikasi.user_id == user["id"])
        .order_by(Notifikasi.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()
    data = []
    for notification in notifications:
        order = await db.get(Pesanan, notification.pesanan_id) if notification.pesanan_id else None
        data.append(notification_payload(notification, order))
    return {"data": data}


@router.get("/unread-count")
async def unread_count(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    result = await db.execute(
        select(func.count(Notifikasi.id)).where(
            Notifikasi.user_id == user["id"],
            Notifikasi.dibaca == False,
        )
    )
    return {"count": int(result.scalar() or 0)}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    notification = await db.get(Notifikasi, notification_id)
    if not notification or notification.user_id != user["id"]:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan.")
    notification.dibaca = True
    await db.commit()
    return {"success": True}


@router.put("/read-all")
async def mark_all_read(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    result = await db.execute(select(Notifikasi).where(Notifikasi.user_id == user["id"], Notifikasi.dibaca == False))
    notifications = result.scalars().all()
    for notification in notifications:
        notification.dibaca = True
    await db.commit()
    return {"success": True, "updated": len(notifications)}


@router.post("/device", status_code=201)
async def register_device(body: DeviceRegistration, request: Request, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    platform = body.platform.lower().strip()
    if platform not in {"android", "web"}:
        raise HTTPException(status_code=400, detail="Platform tidak didukung.")

    result = await db.execute(select(PushDevice).where(PushDevice.token == body.token))
    device = result.scalar_one_or_none()
    if device:
        device.user_id = user["id"]
        device.platform = platform
        device.aktif = True
    else:
        device = PushDevice(user_id=user["id"], token=body.token, platform=platform, aktif=True)
        db.add(device)
    await db.commit()
    await db.refresh(device)
    return {"id": device.id, "platform": device.platform, "aktif": device.aktif}


@router.delete("/device/{device_id}")
async def unregister_device(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = require_customer(request)
    device = await db.get(PushDevice, device_id)
    if not device or device.user_id != user["id"]:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan.")
    device.aktif = False
    await db.commit()
    return {"success": True}
