from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_from_request
from app.config import MARKETPLACE_SCHEMA_ENABLED
from app.database import get_db
from app.models import Layanan, LayananVarian, Mitra, MitraLayanan, Notifikasi, PenugasanMitra, Pesanan, User

router = APIRouter(tags=["operational-readiness-v1"])

ACTIVE_ORDER_STATUSES = {"menunggu","diproses","ditugaskan","menuju_lokasi","dimulai","menunggu_konfirmasi"}
ASSIGNMENT_REQUIRED_STATUSES = {"ditugaskan","menuju_lokasi","dimulai","menunggu_konfirmasi"}


def _private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Cookie"


async def _admin(request: Request, db: AsyncSession) -> User:
    auth = get_user_from_request(request)
    if not auth or not auth.get("id"):
        raise HTTPException(401, "Silakan login terlebih dahulu")
    user = await db.get(User, auth["id"])
    if not user:
        raise HTTPException(401, "Session tidak valid")
    if user.role != "ADMIN":
        raise HTTPException(403, "Akses ditolak. Hanya admin.")
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")
    return user


def _wa_number(value: str | None) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


def _wa_link(phone: str | None, message: str) -> str | None:
    number = _wa_number(phone)
    if not number:
        return None
    return f"https://wa.me/{number}?text={quote(message)}"


@router.get("/api/ops/admin/readiness")
async def readiness_status(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await _admin(request, db)
    _private_no_store(response)

    active_services = (await db.execute(
        select(Layanan.id, Layanan.nama).where(Layanan.aktif == True).order_by(Layanan.nama)  # noqa: E712
    )).all()

    active_partners = (await db.execute(
        select(func.count(Mitra.id)).where(Mitra.aktif == True)  # noqa: E712
    )).scalar_one()

    active_links = (await db.execute(
        select(MitraLayanan.layanan_id)
        .join(Mitra, Mitra.id == MitraLayanan.mitra_id)
        .where(MitraLayanan.aktif == True, Mitra.aktif == True)  # noqa: E712
        .distinct()
    )).scalars().all()
    covered_ids = set(active_links)

    uncovered = [{"id": sid, "nama": nama} for sid, nama in active_services if sid not in covered_ids]

    zero_price_active_variants = (await db.execute(
        select(func.count(LayananVarian.id))
        .join(Layanan, Layanan.id == LayananVarian.layanan_id)
        .where(Layanan.aktif == True, LayananVarian.harga <= 0)  # noqa: E712
    )).scalar_one()

    active_orders = (await db.execute(
        select(func.count(Pesanan.id)).where(Pesanan.status.in_(tuple(ACTIVE_ORDER_STATUSES)))
    )).scalar_one()

    missing_assignment = (await db.execute(
        select(func.count(Pesanan.id))
        .outerjoin(PenugasanMitra, and_(
            PenugasanMitra.pesanan_id == Pesanan.id,
            PenugasanMitra.aktif == True,  # noqa: E712
        ))
        .where(
            Pesanan.status.in_(tuple(ASSIGNMENT_REQUIRED_STATUSES)),
            PenugasanMitra.id.is_(None),
        )
    )).scalar_one()

    duplicate_active_assignments = (await db.execute(
        select(func.count()).select_from(
            select(PenugasanMitra.pesanan_id)
            .where(PenugasanMitra.aktif == True)  # noqa: E712
            .group_by(PenugasanMitra.pesanan_id)
            .having(func.count(PenugasanMitra.id) > 1)
            .subquery()
        )
    )).scalar_one()

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    notifications_24h = (await db.execute(
        select(func.count(Notifikasi.id)).where(Notifikasi.created_at >= since)
    )).scalar_one()

    checks = [
        {"id":"partner_real","label":"Mitra nyata tersedia","ok":int(active_partners or 0)>0,"value":int(active_partners or 0),"detail":"Minimal satu mitra nyata aktif diperlukan sebelum pilot."},
        {"id":"service_coverage","label":"Cakupan mitra per layanan","ok":len(uncovered)==0,"value":len(active_services)-len(uncovered),"detail":f"{len(uncovered)} layanan aktif belum memiliki mitra aktif."},
        {"id":"catalog_price","label":"Harga katalog aktif valid","ok":int(zero_price_active_variants or 0)==0,"value":int(zero_price_active_variants or 0),"detail":"Varian aktif dengan harga <= 0 harus nol."},
        {"id":"assignment_integrity","label":"Integritas penugasan aktif","ok":int(missing_assignment or 0)==0 and int(duplicate_active_assignments or 0)==0,"value":int(missing_assignment or 0)+int(duplicate_active_assignments or 0),"detail":"Tidak boleh ada order yang memerlukan mitra tanpa assignment, atau assignment aktif ganda."},
        {"id":"notification_audit","label":"Audit notifikasi tersedia","ok":True,"value":int(notifications_24h or 0),"detail":"Jumlah notifikasi yang tercatat 24 jam terakhir."},
    ]
    blockers = [c for c in checks if not c["ok"]]

    return {
        "ready_for_pilot": not blockers,
        "checks": checks,
        "blockers": blockers,
        "metrics": {
            "active_services": len(active_services),
            "active_partners": int(active_partners or 0),
            "covered_services": len(active_services) - len(uncovered),
            "uncovered_services": uncovered,
            "active_orders": int(active_orders or 0),
            "missing_assignment": int(missing_assignment or 0),
            "duplicate_active_assignment": int(duplicate_active_assignments or 0),
            "notifications_24h": int(notifications_24h or 0),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/ops/admin/orders/{order_id}/contact")
async def admin_order_contact(order_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await _admin(request, db)
    _private_no_store(response)

    order = (await db.execute(select(Pesanan).where(or_(Pesanan.id == order_id, Pesanan.kode == order_id)))).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    customer = await db.get(User, order.user_id)
    assignment_row = (await db.execute(
        select(PenugasanMitra, Mitra)
        .join(Mitra, Mitra.id == PenugasanMitra.mitra_id)
        .where(PenugasanMitra.pesanan_id == order.id, PenugasanMitra.aktif == True)  # noqa: E712
        .order_by(PenugasanMitra.assigned_at.desc())
        .limit(1)
    )).first()

    customer_name = customer.nama if customer else "Pelanggan"
    customer_link = _wa_link(
        customer.no_hp if customer else None,
        f"Halo {customer_name}, kami dari BantuDulu terkait pesanan {order.kode}. Pesan ini dikirim oleh Admin BantuDulu.",
    )

    partner_payload = None
    if assignment_row:
        assignment, partner = assignment_row
        partner_payload = {
            "id": partner.id,
            "nama": partner.nama,
            "no_hp": partner.no_hp,
            "assignment_status": assignment.status,
            "whatsapp_url": _wa_link(
                partner.no_hp,
                f"Halo {partner.nama}, ada penugasan BantuDulu untuk pesanan {order.kode}. Silakan konfirmasi ketersediaan kepada Admin BantuDulu.",
            ),
        }

    return {
        "order_id": order.id,
        "kode": order.kode,
        "customer": {
            "nama": customer_name,
            "no_hp": customer.no_hp if customer else "",
            "whatsapp_url": customer_link,
        },
        "partner": partner_payload,
    }


@router.get("/api/ops/admin/notifications/recent")
async def recent_notifications(request: Request, response: Response, limit: int = 50, db: AsyncSession = Depends(get_db)):
    await _admin(request, db)
    _private_no_store(response)
    limit = max(1, min(int(limit or 50), 100))
    rows = (await db.execute(
        select(Notifikasi).order_by(Notifikasi.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "pesanan_id": row.pesanan_id,
            "judul": row.judul,
            "pesan": row.pesan,
            "dibaca": row.dibaca,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
