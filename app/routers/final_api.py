from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_token, get_user_from_request, hash_password, set_auth_cookie, verify_password
from app.config import (
    IS_PRODUCTION,
    MARKETPLACE_SCHEMA_ENABLED,
    PAYMENT_BANK_ENABLED,
    PAYMENT_QRIS_ENABLED,
)
from app.database import get_db
from app.models import (
    Alamat,
    ExternalIdentity,
    FormField,
    Layanan,
    LayananVarian,
    Mitra,
    MitraLayanan,
    OrderStatusHistory,
    PaymentTransaction,
    PenugasanMitra,
    Pesanan,
    User,
)
from app.security import (
    auth_rate_key,
    login_limiter,
    register_limiter,
    reject_honeypot,
    verify_google_credential,
    verify_turnstile,
)

router = APIRouter(prefix="/api/final", tags=["final"])


def _norm(v: str | None) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).casefold()


def _phone(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _json_error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _current_user(request: Request, db: AsyncSession) -> User:
    auth = get_user_from_request(request)
    if not auth or not auth.get("id"):
        raise HTTPException(401, "Silakan login terlebih dahulu")
    user = await db.get(User, auth["id"])
    if not user:
        raise HTTPException(401, "Session tidak valid")
    return user


async def _require_admin(request: Request, db: AsyncSession) -> User:
    user = await _current_user(request, db)
    if user.role != "ADMIN":
        raise HTTPException(403, "Akses ditolak. Hanya admin.")
    return user


def _session_response(user: User, redirect: str | None = None) -> JSONResponse:
    token = create_token({"id": user.id, "email": user.email, "nama": user.nama, "role": user.role})
    target = redirect or ("/admin/dashboard" if user.role == "ADMIN" else "/beranda")
    response = JSONResponse({"redirect": target})
    set_auth_cookie(response, token)
    return response


def _validate_schedule(jadwal: str, jam: str) -> tuple[str, str]:
    try:
        parsed = date.fromisoformat(jadwal)
    except Exception as exc:
        raise HTTPException(400, "Tanggal jadwal tidak valid") from exc
    if parsed < date.today():
        raise HTTPException(400, "Tanggal jadwal tidak boleh di masa lalu")
    if (parsed - date.today()).days > 180:
        raise HTTPException(400, "Jadwal maksimal 180 hari ke depan")

    if jam:
        if not re.fullmatch(r"\d{2}:\d{2}", jam):
            raise HTTPException(400, "Format jam tidak valid")
        h, m = [int(x) for x in jam.split(":")]
        if h > 23 or m > 59:
            raise HTTPException(400, "Jam tidak valid")
    return jadwal, jam


def _allowed_payment(method: str) -> bool:
    if method == "cod":
        return True
    if method == "bank":
        return PAYMENT_BANK_ENABLED
    if method == "qris":
        return PAYMENT_QRIS_ENABLED
    return False


@router.post("/login")
async def login(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    identity = str(data.get("identity") or "").strip()
    password = str(data.get("password") or "")
    reject_honeypot(data.get("website"))

    if not identity or not password:
        return _json_error("Nomor HP/email dan password wajib diisi", 400)

    key = auth_rate_key(request, identity)
    if not login_limiter.allowed(key):
        return _json_error("Terlalu banyak percobaan. Coba lagi beberapa saat.", 429)

    await verify_turnstile(str(data.get("turnstile_token") or ""), request)

    phone = _phone(identity)
    stmt = select(User).where(
        or_(
            User.email == identity.lower(),
            User.no_hp == identity,
            User.no_hp == phone,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password):
        login_limiter.hit(key)
        return _json_error("Nomor HP/email atau password salah", 401)

    # Known source-code demo password must never work in production.
    if IS_PRODUCTION and user.email.casefold() == "admin@bantudulu.id" and password == "admin123":
        login_limiter.hit(key)
        return _json_error("Akun admin default harus dirotasi sebelum digunakan.", 403)

    login_limiter.clear(key)
    return _session_response(user)


@router.post("/register")
async def register(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    nama = str(data.get("nama") or "").strip()
    identity = str(data.get("identity") or "").strip()
    password = str(data.get("password") or "")
    reject_honeypot(data.get("website"))

    if not nama or not identity or len(password) < 8:
        return _json_error("Lengkapi data. Password minimal 8 karakter.", 400)

    key = auth_rate_key(request, identity)
    if not register_limiter.allowed(key):
        return _json_error("Terlalu banyak percobaan pendaftaran. Coba lagi beberapa saat.", 429)

    await verify_turnstile(str(data.get("turnstile_token") or ""), request)

    is_email = "@" in identity
    if is_email:
        email = identity.lower()
        if len(email) > 100 or email.count("@") != 1:
            return _json_error("Email tidak valid", 400)
        no_hp = ""
        exists = await db.execute(select(User).where(User.email == email))
    else:
        no_hp = _phone(identity)
        if len(no_hp) < 8 or len(no_hp) > 20:
            return _json_error("Nomor HP tidak valid", 400)
        email = f"{no_hp}@phone.bantudulu.local"
        exists = await db.execute(select(User).where(or_(User.no_hp == no_hp, User.email == email)))

    if exists.scalar_one_or_none():
        register_limiter.hit(key)
        return _json_error("Akun sudah terdaftar", 400)

    user = User(
        nama=nama[:100],
        email=email,
        no_hp=no_hp,
        password=hash_password(password),
        role="CUSTOMER",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    register_limiter.clear(key)
    return _session_response(user)


@router.post("/google")
async def google_login(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    reject_honeypot(data.get("website"))
    await verify_turnstile(str(data.get("turnstile_token") or ""), request)
    identity = await verify_google_credential(str(data.get("credential") or ""))

    existing = await db.execute(select(User).where(User.email == identity["email"]))
    user = existing.scalar_one_or_none()

    if user and user.role == "ADMIN":
        return _json_error("Akun admin harus masuk melalui halaman admin.", 403)

    if not user:
        user = User(
            nama=identity["name"][:100],
            email=identity["email"],
            no_hp="",
            password=hash_password(secrets.token_urlsafe(32)),
            role="CUSTOMER",
            foto=identity["picture"][:255] or None,
        )
        db.add(user)
        await db.flush()

    # Store Google's stable subject when marketplace/security migration is active.
    if MARKETPLACE_SCHEMA_ENABLED:
        provider_subject = f"google:{identity['sub']}"
        row = (
            await db.execute(
                select(ExternalIdentity).where(ExternalIdentity.provider_subject == provider_subject)
            )
        ).scalar_one_or_none()
        if row and row.user_id != user.id:
            await db.rollback()
            return _json_error("Identitas Google sudah terhubung ke akun lain.", 409)
        if not row:
            db.add(
                ExternalIdentity(
                    user_id=user.id,
                    provider="google",
                    subject=identity["sub"],
                    provider_subject=provider_subject,
                    email=identity["email"],
                )
            )

    await db.commit()
    await db.refresh(user)
    return _session_response(user)


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    addr_res = await db.execute(
        select(Alamat)
        .where(Alamat.user_id == user.id)
        .order_by(Alamat.is_default.desc())
    )
    addr = addr_res.scalars().first()
    email = "" if user.email.endswith("@phone.bantudulu.local") else user.email
    return {
        "id": user.id,
        "nama": user.nama,
        "email": email,
        "no_hp": user.no_hp,
        "role": user.role,
        "address": (
            {"id": addr.id, "label": addr.label, "alamat_lengkap": addr.alamat_lengkap}
            if addr
            else None
        ),
    }


@router.put("/me/address")
async def save_address(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    alamat = str(data.get("alamat_lengkap") or "").strip()
    label = str(data.get("label") or "Rumah").strip()[:50]
    if len(alamat) < 5 or len(alamat) > 1200:
        raise HTTPException(400, "Alamat tidak valid")

    result = await db.execute(
        select(Alamat).where(Alamat.user_id == user.id, Alamat.is_default == True)  # noqa: E712
    )
    row = result.scalar_one_or_none()
    if not row:
        row = Alamat(user_id=user.id, label=label, alamat_lengkap=alamat, is_default=True)
        db.add(row)
    else:
        row.label = label
        row.alamat_lengkap = alamat
    await db.commit()
    return {"success": True}


@router.get("/orders")
async def orders(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(Pesanan)
        .where(Pesanan.user_id == user.id)
        .order_by(Pesanan.created_at.desc())
    )
    out = []
    for p in result.scalars().all():
        l = await db.get(Layanan, p.layanan_id)
        v = await db.get(LayananVarian, p.varian_id)
        payment = "cod"
        try:
            payment = (json.loads(p.form_data or "{}") or {}).get("metode_pembayaran", "cod")
        except Exception:
            pass
        out.append(
            {
                "id": p.id,
                "kode": p.kode,
                "status": p.status,
                "layanan_nama": l.nama if l else "Pesanan",
                "varian_nama": v.nama if v else "",
                "alamat": p.alamat,
                "jadwal": p.jadwal,
                "jam": p.jam,
                "durasi": p.durasi,
                "total_harga": p.total_harga,
                "catatan": p.catatan or "",
                "metode_pembayaran": payment,
                "created_at": p.created_at.isoformat(),
                "created_label": p.created_at.strftime("%d/%m/%Y"),
            }
        )
    return out


@router.get("/orders/{order_id}")
async def order_detail(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(Pesanan).where(
            or_(Pesanan.id == order_id, Pesanan.kode == order_id),
            Pesanan.user_id == user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    l = await db.get(Layanan, p.layanan_id)
    v = await db.get(LayananVarian, p.varian_id)
    return {
        "id": p.id,
        "kode": p.kode,
        "status": p.status,
        "layanan_nama": l.nama if l else "Pesanan",
        "varian_nama": v.nama if v else "",
        "alamat": p.alamat,
        "jadwal": p.jadwal,
        "jam": p.jam,
        "durasi": p.durasi,
        "total_harga": p.total_harga,
        "catatan": p.catatan or "",
        "form_data": p.form_data,
        "created_at": p.created_at.isoformat(),
    }


async def _find_service(db: AsyncSession, name: str) -> Layanan | None:
    result = await db.execute(select(Layanan).where(Layanan.aktif == True))  # noqa: E712
    services = result.scalars().all()
    for service in services:
        if _norm(service.nama) == _norm(name):
            return service

    aliases = {"pijat & relaksasi": {"trapis", "pijat & relaksasi"}}
    wanted = _norm(name)
    for names in aliases.values():
        normalized = {_norm(x) for x in names}
        if wanted in normalized:
            return next((s for s in services if _norm(s.nama) in normalized), None)
    return None


@router.post("/orders")
async def create_order(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)

    service_name = str(data.get("service_name") or "").strip()
    variant_name = str(data.get("variant_name") or "").strip()
    if not service_name or not variant_name:
        raise HTTPException(400, "Layanan dan varian wajib dipilih")

    service = await _find_service(db, service_name)
    if not service:
        raise HTTPException(404, f"Layanan tidak ditemukan: {service_name}")

    variants = (
        await db.execute(
            select(LayananVarian).where(LayananVarian.layanan_id == service.id)
        )
    ).scalars().all()
    variant = next((v for v in variants if _norm(v.nama) == _norm(variant_name)), None)
    if not variant and len(variants) == 1:
        variant = variants[0]
    if not variant:
        raise HTTPException(400, f"Varian layanan tidak ditemukan: {variant_name}")

    raw_duration = int(data.get("duration") or 1)
    duration = max(1, min(raw_duration, 24))
    if service.tipe_hitung not in {"per_jam", "per_unit"}:
        duration = 1

    alamat = str(data.get("address") or "").strip()
    jadwal = str(data.get("jadwal") or "").strip()
    jam = str(data.get("jam") or "").strip()
    catatan = str(data.get("catatan") or "").strip()
    payment = str(data.get("metode_pembayaran") or "cod").strip().lower()

    if len(alamat) < 5 or len(alamat) > 1200:
        raise HTTPException(400, "Alamat wajib diisi dengan benar")
    if len(catatan) > 2000:
        raise HTTPException(400, "Catatan terlalu panjang")
    _validate_schedule(jadwal, jam)

    if not _allowed_payment(payment):
        raise HTTPException(400, "Metode pembayaran belum tersedia")

    extras = data.get("extras") if isinstance(data.get("extras"), dict) else {}
    selected_addons = extras.get("addons") if isinstance(extras.get("addons"), list) else []
    selected_addons = [str(x)[:100] for x in selected_addons[:20]]

    addon_total = 0
    fields = (
        await db.execute(select(FormField).where(FormField.layanan_id == service.id))
    ).scalars().all()
    addon_prices = {_norm(x): 0 for x in selected_addons}
    for field in fields:
        label = _norm(field.label.replace("+", ""))
        for key in list(addon_prices):
            if key == label or key in label or label in key:
                addon_prices[key] = max(0, int(field.harga_tambahan or 0))
    addon_total += sum(addon_prices.values())

    if extras.get("floor2") and _norm(service.nama) == _norm("Cuci Tandon Air"):
        addon_total += 50000

    total = int(variant.harga) * duration + addon_total
    if total <= 0 or total > 100_000_000:
        raise HTTPException(400, "Total pesanan tidak valid")

    import uuid

    kode = f"BD-{uuid.uuid4().hex[:6].upper()}"
    form = {"metode_pembayaran": payment, "extras": extras}
    order = Pesanan(
        user_id=user.id,
        layanan_id=service.id,
        varian_id=variant.id,
        kode=kode,
        status="menunggu",
        alamat=alamat,
        jadwal=jadwal,
        jam=jam,
        durasi=duration,
        total_harga=total,
        catatan=catatan,
        form_data=json.dumps(form, ensure_ascii=False),
    )
    db.add(order)
    await db.flush()

    if MARKETPLACE_SCHEMA_ENABLED:
        db.add(
            OrderStatusHistory(
                pesanan_id=order.id,
                status_from=None,
                status_to="menunggu",
                changed_by_user_id=user.id,
                catatan="Pesanan dibuat",
            )
        )
        db.add(
            PaymentTransaction(
                pesanan_id=order.id,
                method=payment,
                status="cash_on_delivery" if payment == "cod" else "pending",
                amount=total,
                provider="manual" if payment != "cod" else None,
            )
        )

    await db.commit()
    await db.refresh(order)
    return {
        "success": True,
        "data": {
            "id": order.id,
            "kode": order.kode,
            "status": order.status,
            "total_harga": order.total_harga,
        },
    }


@router.put("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(Pesanan).where(Pesanan.id == order_id, Pesanan.user_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    if order.status not in {"menunggu", "diproses", "ditugaskan"}:
        raise HTTPException(400, "Pesanan pada status ini tidak dapat dibatalkan")

    old_status = order.status
    order.status = "dibatalkan"
    if MARKETPLACE_SCHEMA_ENABLED:
        db.add(
            OrderStatusHistory(
                pesanan_id=order.id,
                status_from=old_status,
                status_to="dibatalkan",
                changed_by_user_id=user.id,
                catatan="Dibatalkan customer",
            )
        )
    await db.commit()
    return {"success": True, "status": order.status}


# ── Marketplace admin APIs ──

@router.get("/admin/partners")
async def admin_partners(request: Request, db: AsyncSession = Depends(get_db)):
    await _require_admin(request, db)
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")
    rows = (await db.execute(select(Mitra).order_by(Mitra.nama))).scalars().all()
    return [
        {
            "id": row.id,
            "nama": row.nama,
            "no_hp": row.no_hp,
            "email": row.email,
            "status": row.status,
            "aktif": row.aktif,
            "rating": row.rating,
            "total_jobs": row.total_jobs,
        }
        for row in rows
    ]


@router.post("/admin/partners")
async def admin_create_partner(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    await _require_admin(request, db)
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")

    nama = str(data.get("nama") or "").strip()
    no_hp = _phone(str(data.get("no_hp") or ""))
    email = str(data.get("email") or "").strip().lower() or None
    layanan_ids = data.get("layanan_ids") if isinstance(data.get("layanan_ids"), list) else []

    if not nama or len(no_hp) < 8:
        raise HTTPException(400, "Nama dan nomor HP mitra wajib diisi")

    partner = Mitra(nama=nama[:120], no_hp=no_hp, email=email)
    db.add(partner)
    await db.flush()

    for layanan_id in {str(x) for x in layanan_ids[:100]}:
        service = await db.get(Layanan, layanan_id)
        if service:
            db.add(
                MitraLayanan(
                    key=f"{partner.id}:{service.id}",
                    mitra_id=partner.id,
                    layanan_id=service.id,
                    aktif=True,
                )
            )

    await db.commit()
    await db.refresh(partner)
    return {"success": True, "id": partner.id}


@router.put("/admin/partners/{partner_id}")
async def admin_update_partner(
    partner_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(request, db)
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")
    partner = await db.get(Mitra, partner_id)
    if not partner:
        raise HTTPException(404, "Mitra tidak ditemukan")

    if "nama" in data:
        partner.nama = str(data["nama"] or "").strip()[:120] or partner.nama
    if "no_hp" in data:
        phone = _phone(str(data["no_hp"] or ""))
        if len(phone) < 8:
            raise HTTPException(400, "Nomor HP mitra tidak valid")
        partner.no_hp = phone
    if "email" in data:
        partner.email = str(data["email"] or "").strip().lower() or None
    if "status" in data:
        status = str(data["status"] or "").strip().lower()
        if status not in {"tersedia", "sibuk", "nonaktif"}:
            raise HTTPException(400, "Status mitra tidak valid")
        partner.status = status
    if "aktif" in data:
        partner.aktif = bool(data["aktif"])

    await db.commit()
    return {"success": True}


@router.post("/admin/orders/{order_id}/assign")
async def admin_assign_order(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _require_admin(request, db)
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")

    order = await db.get(Pesanan, order_id)
    partner = await db.get(Mitra, str(data.get("mitra_id") or ""))
    if not order:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    if not partner or not partner.aktif:
        raise HTTPException(404, "Mitra tidak tersedia")

    current = (
        await db.execute(
            select(PenugasanMitra).where(
                PenugasanMitra.pesanan_id == order.id,
                PenugasanMitra.aktif == True,  # noqa: E712
            )
        )
    ).scalars().all()
    for row in current:
        row.aktif = False

    old_status = order.status
    order.status = "ditugaskan"
    db.add(
        PenugasanMitra(
            pesanan_id=order.id,
            mitra_id=partner.id,
            assigned_by_user_id=admin.id,
            status="ditugaskan",
            aktif=True,
        )
    )
    db.add(
        OrderStatusHistory(
            pesanan_id=order.id,
            status_from=old_status,
            status_to="ditugaskan",
            changed_by_user_id=admin.id,
            catatan=f"Ditugaskan ke mitra {partner.nama}",
        )
    )
    await db.commit()
    return {"success": True, "status": order.status, "mitra_id": partner.id}


@router.get("/admin/transactions")
async def admin_transactions(request: Request, db: AsyncSession = Depends(get_db)):
    await _require_admin(request, db)
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")
    rows = (
        await db.execute(
            select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": row.id,
            "pesanan_id": row.pesanan_id,
            "method": row.method,
            "status": row.status,
            "amount": row.amount,
            "provider": row.provider,
            "reference_id": row.reference_id,
            "created_at": row.created_at.isoformat(),
            "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        }
        for row in rows
    ]
