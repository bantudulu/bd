import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_password
from app.database import get_db
from app.mobile_auth import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_DAYS, create_mobile_access_token, decode_mobile_access_token, generate_refresh_token, hash_refresh_token, refresh_expiry
from app.models import FormField, Layanan, LayananVarian, Notifikasi, Pesanan, User
from app.models_mobile import MobileSession, OrderIdempotency
from app.models_push import PushDevice
from app.query_services import catalog_maps, order_related_maps, variants_by_service
from app.routers.api_pesanan import CreatePesananBody, create_pesanan

router = APIRouter(prefix="/api/v1", tags=["mobile-v1"])


def ok(data: Any = None, *, meta: dict | None = None) -> dict:
    payload = {"ok": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return payload


def _bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    if not value.lower().startswith("bearer "):
        return None
    token = value[7:].strip()
    return token or None


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def require_mobile_customer(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Access token diperlukan.")
    payload = decode_mobile_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Access token tidak valid atau sudah kedaluwarsa.")
    if payload.get("role") != "CUSTOMER":
        raise HTTPException(status_code=403, detail="Endpoint ini hanya untuk customer.")
    session = await db.get(MobileSession, payload.get("sid"))
    if not session or not session.aktif or session.user_id != payload.get("sub"):
        raise HTTPException(status_code=401, detail="Sesi perangkat sudah tidak aktif.")
    if _aware_utc(session.expires_at) <= datetime.now(timezone.utc):
        session.aktif = False
        await db.commit()
        raise HTTPException(status_code=401, detail="Sesi perangkat sudah kedaluwarsa.")
    return payload


class MobileLoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=200)
    device_id: str | None = Field(default=None, max_length=160)
    device_name: str | None = Field(default=None, max_length=120)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class DeviceBody(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    platform: str = Field(default="android", min_length=3, max_length=20)


def _session_tokens(user: User, session: MobileSession, refresh_token: str) -> dict:
    return {
        "access_token": create_mobile_access_token(user_id=user.id, email=user.email, nama=user.nama, role=user.role, session_id=session.id),
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "refresh_token": refresh_token,
        "refresh_expires_in": REFRESH_TOKEN_DAYS * 86400,
    }


@router.post("/auth/login")
async def mobile_login(body: MobileLoginBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    user = result.scalar_one_or_none()
    if not user or user.role != "CUSTOMER" or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Email atau password salah.")
    raw_refresh = generate_refresh_token()
    session = MobileSession(user_id=user.id, refresh_token_hash=hash_refresh_token(raw_refresh), device_id=body.device_id.strip() if body.device_id else None, device_name=body.device_name.strip() if body.device_name else None, expires_at=refresh_expiry(), aktif=True)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ok({"user": {"id": user.id, "nama": user.nama, "email": user.email, "no_hp": user.no_hp, "role": user.role}, "session_id": session.id, **_session_tokens(user, session, raw_refresh)})


@router.post("/auth/refresh")
async def mobile_refresh(body: RefreshBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MobileSession).where(MobileSession.refresh_token_hash == hash_refresh_token(body.refresh_token)))
    session = result.scalar_one_or_none()
    if not session or not session.aktif:
        raise HTTPException(status_code=401, detail="Refresh token tidak valid.")
    if _aware_utc(session.expires_at) <= datetime.now(timezone.utc):
        session.aktif = False
        await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token sudah kedaluwarsa.")
    user = await db.get(User, session.user_id)
    if not user or user.role != "CUSTOMER":
        session.aktif = False
        await db.commit()
        raise HTTPException(status_code=401, detail="User session tidak valid.")
    new_refresh = generate_refresh_token()
    session.refresh_token_hash = hash_refresh_token(new_refresh)
    session.expires_at = refresh_expiry()
    await db.commit()
    return ok({"session_id": session.id, **_session_tokens(user, session, new_refresh)})


@router.post("/auth/logout")
async def mobile_logout(user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    session = await db.get(MobileSession, user["sid"])
    if session:
        session.aktif = False
        await db.commit()
    return ok({"logged_out": True})


@router.get("/auth/me")
async def mobile_me(user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    row = await db.get(User, user["sub"])
    if not row:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    return ok({"id": row.id, "nama": row.nama, "email": row.email, "no_hp": row.no_hp, "role": row.role})


@router.get("/services")
async def services(user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Layanan).where(Layanan.aktif == True).order_by(Layanan.nama.asc()))  # noqa: E712
    rows = list(result.scalars().all())
    category_map, prices = await catalog_maps(db, rows)
    return ok([{"id": row.id, "nama": row.nama, "deskripsi": row.deskripsi, "jenis_layanan": row.jenis_layanan, "tipe_hitung": row.tipe_hitung, "gambar_url": row.gambar_url, "kategori": {"id": cat.id, "nama": cat.nama, "slug": cat.slug, "icon": cat.icon} if (cat := category_map.get(row.kategori_id)) else None, "harga_min": prices.get(row.id, 0)} for row in rows])


@router.get("/services/{service_id}")
async def service_detail(service_id: str, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    service = await db.get(Layanan, service_id)
    if not service or not service.aktif:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan.")
    category_map, _ = await catalog_maps(db, [service])
    variants = (await variants_by_service(db, [service.id])).get(service.id, [])
    fields_result = await db.execute(select(FormField).where(FormField.layanan_id == service.id).order_by(FormField.urutan.asc()))
    fields = fields_result.scalars().all()
    category = category_map.get(service.kategori_id)
    return ok({"id": service.id, "nama": service.nama, "deskripsi": service.deskripsi, "catatan": service.catatan, "jenis_layanan": service.jenis_layanan, "tipe_hitung": service.tipe_hitung, "gambar_url": service.gambar_url, "kategori": {"id": category.id, "nama": category.nama, "slug": category.slug, "icon": category.icon} if category else None, "varian": [{"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi} for v in variants], "form_fields": [{"id": f.id, "label": f.label, "field_type": f.field_type, "required": f.required, "harga_tambahan": f.harga_tambahan, "options": json.loads(f.options) if f.options else []} for f in fields]})


def _order_link(order: Pesanan) -> dict:
    return {"deep_link": f"bantudulu://orders/{order.kode}", "web_path": f"/pesanan/{order.kode}"}


def _order_payload_from_maps(order: Pesanan, related: dict) -> dict:
    service = related["services"].get(order.layanan_id)
    variant = related["variants"].get(order.varian_id)
    assignment = related["assignments"].get(order.id)
    worker = related["workers"].get(assignment.petugas_id) if assignment else None
    assignment_payload = {"id": assignment.id, "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None, "petugas": {"id": worker.id, "nama": worker.nama, "foto": worker.foto, "wilayah": worker.wilayah} if worker else None} if assignment else None
    return {"id": order.id, "kode": order.kode, "status": order.status, "layanan": {"id": service.id, "nama": service.nama} if service else None, "varian": {"id": variant.id, "nama": variant.nama} if variant else None, "jadwal": order.jadwal, "jam": order.jam, "durasi": order.durasi, "alamat": order.alamat, "catatan": order.catatan, "total_harga": order.total_harga, "assignment": assignment_payload, "links": _order_link(order), "created_at": order.created_at.isoformat() if order.created_at else None, "updated_at": order.updated_at.isoformat() if order.updated_at else None}


@router.get("/orders")
async def orders(status: str | None = None, limit: int = 30, offset: int = 0, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 100)); offset = max(0, offset)
    stmt = select(Pesanan).where(Pesanan.user_id == user["sub"])
    if status:
        stmt = stmt.where(Pesanan.status == status.strip().lower())
    result = await db.execute(stmt.order_by(Pesanan.created_at.desc()).offset(offset).limit(limit))
    rows = list(result.scalars().all())
    related = await order_related_maps(db, rows)
    return ok([_order_payload_from_maps(row, related) for row in rows], meta={"limit": limit, "offset": offset, "count": len(rows)})


@router.get("/orders/{identifier}")
async def order_detail(identifier: str, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pesanan).where(Pesanan.user_id == user["sub"], ((Pesanan.id == identifier) | (Pesanan.kode == identifier))))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan.")
    related = await order_related_maps(db, [order])
    return ok(_order_payload_from_maps(order, related))


def _request_fingerprint(body: CreatePesananBody) -> str:
    raw = json.dumps(body.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@router.post("/orders", status_code=201)
async def create_mobile_order(body: CreatePesananBody, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    if not idempotency_key or not (8 <= len(idempotency_key.strip()) <= 100):
        raise HTTPException(status_code=400, detail="Header Idempotency-Key (8-100 karakter) wajib untuk membuat pesanan.")
    key = idempotency_key.strip(); request_hash = _request_fingerprint(body)
    result = await db.execute(select(OrderIdempotency).where(OrderIdempotency.user_id == user["sub"], OrderIdempotency.idempotency_key == key))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key sudah digunakan untuk payload yang berbeda.")
        if not existing.pesanan_id:
            raise HTTPException(status_code=409, detail="Request dengan Idempotency-Key ini sedang diproses. Coba lagi sebentar.")
        order = await db.get(Pesanan, existing.pesanan_id)
        if not order:
            raise HTTPException(status_code=409, detail="Hasil request idempotent tidak tersedia.")
        return ok(_order_payload_from_maps(order, await order_related_maps(db, [order])), meta={"idempotent_replay": True})
    claim = OrderIdempotency(user_id=user["sub"], idempotency_key=key, request_hash=request_hash, pesanan_id=None)
    db.add(claim)
    try:
        await db.commit(); await db.refresh(claim)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Idempotency-Key sedang diproses oleh request lain.")
    try:
        legacy_result = await create_pesanan(request=request, data=body, db=db)
        order = await db.get(Pesanan, legacy_result["data"]["id"])
        if not order:
            raise RuntimeError("Pesanan berhasil dibuat tetapi tidak dapat dimuat kembali.")
        claim = await db.get(OrderIdempotency, claim.id); claim.pesanan_id = order.id
        await db.commit()
        return ok(_order_payload_from_maps(order, await order_related_maps(db, [order])), meta={"idempotent_replay": False})
    except Exception:
        await db.rollback()
        raise


@router.get("/notifications")
async def notifications(limit: int = 50, offset: int = 0, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 100)); offset = max(0, offset)
    result = await db.execute(select(Notifikasi).where(Notifikasi.user_id == user["sub"]).order_by(Notifikasi.created_at.desc()).offset(offset).limit(limit))
    rows = list(result.scalars().all())
    order_ids = {row.pesanan_id for row in rows if row.pesanan_id}
    order_map = {}
    if order_ids:
        order_result = await db.execute(select(Pesanan).where(Pesanan.id.in_(order_ids)))
        order_map = {row.id: row for row in order_result.scalars().all()}
    data = []
    for row in rows:
        order = order_map.get(row.pesanan_id)
        data.append({"id": row.id, "judul": row.judul, "pesan": row.pesan, "dibaca": row.dibaca, "created_at": row.created_at.isoformat() if row.created_at else None, "order_code": order.kode if order else None, "deep_link": f"bantudulu://orders/{order.kode}" if order else None})
    return ok(data, meta={"limit": limit, "offset": offset, "count": len(data)})


@router.get("/notifications/unread-count")
async def notification_unread_count(user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(Notifikasi.id)).where(Notifikasi.user_id == user["sub"], Notifikasi.dibaca == False))  # noqa: E712
    return ok({"count": int(result.scalar() or 0)})


@router.put("/notifications/{notification_id}/read")
async def notification_read(notification_id: str, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    row = await db.get(Notifikasi, notification_id)
    if not row or row.user_id != user["sub"]:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan.")
    row.dibaca = True; await db.commit()
    return ok({"updated": True})


@router.post("/devices")
async def register_mobile_device(body: DeviceBody, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    platform = body.platform.lower().strip()
    if platform != "android":
        raise HTTPException(status_code=400, detail="API mobile v1 hanya menerima platform android.")
    result = await db.execute(select(PushDevice).where(PushDevice.token == body.token))
    device = result.scalar_one_or_none()
    if device:
        device.user_id = user["sub"]; device.platform = platform; device.aktif = True
    else:
        device = PushDevice(user_id=user["sub"], token=body.token, platform=platform, aktif=True); db.add(device)
    await db.commit(); await db.refresh(device)
    return ok({"id": device.id, "platform": device.platform, "aktif": device.aktif})


@router.delete("/devices/{device_id}")
async def unregister_mobile_device(device_id: str, user=Depends(require_mobile_customer), db: AsyncSession = Depends(get_db)):
    device = await db.get(PushDevice, device_id)
    if not device or device.user_id != user["sub"]:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan.")
    device.aktif = False; await db.commit()
    return ok({"unregistered": True})
