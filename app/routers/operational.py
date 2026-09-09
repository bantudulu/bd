from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_from_request
from app.config import MARKETPLACE_SCHEMA_ENABLED
from app.database import get_db
from app.operational_policy import OPERATIONAL_V1_CUTOFF_DB, is_pre_operational_v1
from app.models import (
    FormField,
    Kategori,
    Layanan,
    LayananVarian,
    Mitra,
    MitraLayanan,
    Notifikasi,
    OrderStatusHistory,
    PaymentTransaction,
    PenugasanMitra,
    Pesanan,
    User,
)

router = APIRouter(tags=["operational-v1"])

INTERNAL_ACTIVE = {
    "menunggu",
    "diproses",
    "ditugaskan",
    "menuju_lokasi",
    "dimulai",
    "menunggu_konfirmasi",
}
TERMINAL = {"selesai", "dibatalkan"}


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _phone(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _utcnow_db() -> datetime:
    """UTC-naive datetime matching production TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _public_status(status: str | None) -> dict:
    status = _norm(status)
    if status in {"menunggu", "diproses", "ditugaskan"}:
        return {
            "code": "diterima",
            "label": "Pesanan diterima BantuDulu",
            "description": "Pesanan Anda sudah diterima dan sedang kami siapkan.",
        }
    if status in {"menuju_lokasi", "dimulai", "menunggu_konfirmasi"}:
        return {
            "code": "menuju_lokasi",
            "label": "Tim BantuDulu sedang menuju lokasi Anda",
            "description": "Tim BantuDulu sedang menangani pesanan Anda.",
        }
    if status == "selesai":
        return {
            "code": "selesai",
            "label": "Selesai",
            "description": "Pesanan telah diselesaikan oleh BantuDulu.",
        }
    if status == "dibatalkan":
        return {
            "code": "dibatalkan",
            "label": "Dibatalkan",
            "description": "Pesanan telah dibatalkan.",
        }
    return {
        "code": "diterima",
        "label": "Pesanan diterima BantuDulu",
        "description": "Pesanan Anda sedang kami proses.",
    }


async def _current_user(request: Request, db: AsyncSession) -> User:
    auth = get_user_from_request(request)
    if not auth or not auth.get("id"):
        raise HTTPException(401, "Silakan login terlebih dahulu")
    user = await db.get(User, auth["id"])
    if not user:
        raise HTTPException(401, "Session tidak valid")
    return user


async def _admin(request: Request, db: AsyncSession) -> User:
    user = await _current_user(request, db)
    if user.role != "ADMIN":
        raise HTTPException(403, "Akses ditolak. Hanya admin.")
    if not MARKETPLACE_SCHEMA_ENABLED:
        raise HTTPException(503, "Marketplace schema belum diaktifkan")
    return user


async def _find_order(db: AsyncSession, order_id: str) -> Pesanan:
    order = (
        await db.execute(
            select(Pesanan).where(
                or_(Pesanan.id == order_id, Pesanan.kode == order_id)
            )
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    return order


async def _active_assignment(
    db: AsyncSession,
    order_id: str,
) -> PenugasanMitra | None:
    return (
        await db.execute(
            select(PenugasanMitra)
            .where(
                PenugasanMitra.pesanan_id == order_id,
                PenugasanMitra.aktif == True,  # noqa: E712
            )
            .order_by(PenugasanMitra.assigned_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_payment(
    db: AsyncSession,
    order_id: str,
) -> PaymentTransaction | None:
    return (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.pesanan_id == order_id)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _order_form_data(order: Pesanan) -> dict:
    try:
        data = json.loads(order.form_data or "{}") or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _payment_method(order: Pesanan) -> str:
    data = _order_form_data(order)
    return str(data.get("metode_pembayaran") or "cod").strip().lower()


def _distance_surcharge(distance_km: float) -> int:
    excess_km = max(0.0, float(distance_km) - 5.0)
    return int(math.ceil(excess_km)) * 10000


def _safe_nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _is_legacy_order(order: Pesanan) -> bool:
    # Explicit migration boundary prevents pre-Operational-V1 rows from being
    # treated as live work merely because an old status is still non-terminal.
    return (
        is_pre_operational_v1(order.created_at)
        or not str(order.alamat or "").strip()
        or not str(order.jadwal or "").strip()
        or not str(order.jam or "").strip()
        or _payment_method(order) != "cod"
    )


def _customer_public_status(order: Pesanan) -> dict:
    status = _norm(order.status)
    if _is_legacy_order(order) and status not in TERMINAL:
        return {
            "code": "arsip",
            "label": "Riwayat pesanan lama",
            "description": "Pesanan ini berasal dari data lama dan tidak termasuk pesanan aktif BantuDulu saat ini.",
        }
    return _public_status(order.status)


def _customer_payment_label(order: Pesanan) -> str:
    method = _payment_method(order)
    if method == "cod":
        return "Bayar di Tempat (COD)"
    if method == "transfer":
        return "Transfer Bank (riwayat lama)"
    if method == "qris":
        return "QRIS (riwayat lama)"
    return f"{method.upper()} (riwayat lama)"


def _assert_status(order: Pesanan, allowed: set[str], action: str) -> None:
    if _is_legacy_order(order):
        raise HTTPException(409, "Pesanan aktif lama/arsip tidak dapat diubah melalui flow Operational V1.")
    if order.status not in allowed:
        raise HTTPException(
            409,
            f"{action} tidak dapat dilakukan dari status {order.status}.",
        )


async def _history(
    db: AsyncSession,
    order: Pesanan,
    admin_id: str,
    old_status: str | None,
    new_status: str,
    note: str,
) -> None:
    db.add(
        OrderStatusHistory(
            pesanan_id=order.id,
            status_from=old_status,
            status_to=new_status,
            changed_by_user_id=admin_id,
            catatan=note,
        )
    )


async def _customer_notification(
    db: AsyncSession,
    order: Pesanan,
    title: str,
    message: str,
) -> None:
    db.add(
        Notifikasi(
            user_id=order.user_id,
            pesanan_id=order.id,
            judul=title,
            pesan=message,
        )
    )


def _admin_payload_from_parts(
    order: Pesanan,
    customer_name: str | None,
    customer_phone: str | None,
    service_name: str | None,
    variant_name: str | None,
    assignment: PenugasanMitra | None = None,
    partner: Mitra | None = None,
    payment: PaymentTransaction | None = None,
) -> dict:
    form_data = _order_form_data(order)
    extras = form_data.get("extras") if isinstance(form_data.get("extras"), dict) else {}
    distance_eligible = _norm(service_name) in {"trapis", "pijat & relaksasi"}
    distance_policy = (
        extras.get("distance_policy")
        if isinstance(extras.get("distance_policy"), dict)
        else {}
    )
    distance_confirmed = distance_policy.get("confirmed_by_admin") is True
    return {
        "id": order.id,
        "kode": order.kode,
        "status": order.status,
        "pelanggan_nama": customer_name or "-",
        "pelanggan_wa": customer_phone or "",
        "layanan_id": order.layanan_id,
        "layanan_nama": service_name or "Pesanan",
        "varian_nama": variant_name or "",
        "alamat": order.alamat,
        "jadwal": order.jadwal,
        "jam": order.jam,
        "durasi": order.durasi,
        "catatan": order.catatan or "",
        "total_harga": order.total_harga,
        "metode_pembayaran": payment.method if payment else _payment_method(order),
        "status_pembayaran": payment.status if payment else "belum_tercatat",
        "extras": extras,
        "distance_pricing": {
            "eligible": distance_eligible,
            "distance_km": extras.get("distance_km") if distance_confirmed else None,
            "surcharge": (
                _safe_nonnegative_int(extras.get("distance_surcharge"))
                if distance_confirmed
                else 0
            ),
            "free_km": 5,
            "rate_per_km": 10000,
        },
        "mitra": (
            {
                "id": partner.id,
                "nama": partner.nama,
                "no_hp": partner.no_hp,
                "status": partner.status,
                "assignment_status": assignment.status,
            }
            if partner and assignment
            else None
        ),
        "is_legacy": _is_legacy_order(order),
        "created_at": order.created_at.isoformat(),
    }


def _private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Cookie"


def _page_values(page: int, page_size: int, default_size: int) -> tuple[int, int]:
    safe_page = max(int(page or 1), 1)
    safe_size = int(page_size or default_size)
    safe_size = max(1, min(safe_size, 50))
    return safe_page, safe_size


def _current_order_conditions():
    return (
        Pesanan.created_at >= OPERATIONAL_V1_CUTOFF_DB,
        func.length(func.trim(func.coalesce(Pesanan.alamat, ""))) > 0,
        func.length(func.trim(func.coalesce(Pesanan.jadwal, ""))) > 0,
        func.length(func.trim(func.coalesce(Pesanan.jam, ""))) > 0,
    )

# ── Customer-safe order tracking ──────────────────────────────────────────────

# ── Customer-safe order tracking ──────────────────────────────────────────────

@router.get("/api/ops/customer/orders")
async def customer_orders(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 12,
    view: str = "active",
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    _private_no_store(response)
    page, page_size = _page_values(page, page_size, 12)

    view = _norm(view)
    conditions = [Pesanan.user_id == user.id]
    if view == "active":
        conditions.append(Pesanan.status.in_(tuple(INTERNAL_ACTIVE)))
        conditions.extend(_current_order_conditions())
    elif view in {"selesai", "dibatalkan"}:
        conditions.append(Pesanan.status == view)
    elif view != "all":
        view = "active"
        conditions.append(Pesanan.status.in_(tuple(INTERNAL_ACTIVE)))
        conditions.extend(_current_order_conditions())

    total = (
        await db.execute(select(func.count(Pesanan.id)).where(*conditions))
    ).scalar_one()

    rows = (
        await db.execute(
            select(
                Pesanan,
                Layanan.nama.label("layanan_nama"),
                LayananVarian.nama.label("varian_nama"),
            )
            .outerjoin(Layanan, Layanan.id == Pesanan.layanan_id)
            .outerjoin(LayananVarian, LayananVarian.id == Pesanan.varian_id)
            .where(*conditions)
            .order_by(Pesanan.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = []
    for order, service_name, variant_name in rows:
        items.append(
            {
                "id": order.id,
                "kode": order.kode,
                "status": _customer_public_status(order),
                "layanan_nama": service_name or "Pesanan",
                "varian_nama": variant_name or "",
                "jadwal": order.jadwal,
                "jam": order.jam,
                "total_harga": order.total_harga,
                "is_legacy": _is_legacy_order(order),
                "created_at": order.created_at.isoformat(),
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
        "has_more": page * page_size < int(total or 0),
        "view": view,
    }

@router.get("/api/ops/customer/orders/{order_id}")
async def customer_order_detail(
    order_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    _private_no_store(response)

    row = (
        await db.execute(
            select(
                Pesanan,
                Layanan.nama.label("layanan_nama"),
                LayananVarian.nama.label("varian_nama"),
            )
            .outerjoin(Layanan, Layanan.id == Pesanan.layanan_id)
            .outerjoin(LayananVarian, LayananVarian.id == Pesanan.varian_id)
            .where(
                Pesanan.user_id == user.id,
                or_(Pesanan.id == order_id, Pesanan.kode == order_id),
            )
            .limit(1)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    order, service_name, variant_name = row
    return {
        "id": order.id,
        "kode": order.kode,
        "status": _customer_public_status(order),
        "layanan_nama": service_name or "Pesanan",
        "varian_nama": variant_name or "",
        "alamat": order.alamat,
        "jadwal": order.jadwal,
        "jam": order.jam,
        "durasi": order.durasi,
        "total_harga": order.total_harga,
        "catatan": order.catatan or "",
        "metode_pembayaran": _payment_method(order),
        "metode_pembayaran_label": _customer_payment_label(order),
        "is_legacy": _is_legacy_order(order),
        "legacy_note": (
            "Sebagian detail pesanan lama tidak tercatat pada sistem sebelumnya."
            if _is_legacy_order(order)
            else ""
        ),
        "created_at": order.created_at.isoformat(),
    }

# ── Admin dashboard / orders ──────────────────────────────────────────────────

# ── Admin dashboard / orders ──────────────────────────────────────────────────

@router.get("/api/ops/admin/summary")
async def admin_summary(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    _private_no_store(response)

    customer_count = (
        select(func.count(User.id))
        .where(User.role == "CUSTOMER")
        .scalar_subquery()
    )
    active_partner_count = (
        select(func.count(Mitra.id))
        .where(Mitra.aktif == True)  # noqa: E712
        .scalar_subquery()
    )
    active_service_count = (
        select(func.count(Layanan.id))
        .where(Layanan.aktif == True)  # noqa: E712
        .scalar_subquery()
    )
    current_scope = and_(*_current_order_conditions())

    row = (
        await db.execute(
            select(
                func.count(Pesanan.id).label("total_order"),
                func.coalesce(
                    func.sum(case((and_(current_scope, Pesanan.status == "menunggu"), 1), else_=0)),
                    0,
                ).label("pesanan_baru"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    current_scope,
                                    Pesanan.status.in_(("diproses", "ditugaskan", "menuju_lokasi", "dimulai")),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("sedang_diproses"),
                func.coalesce(
                    func.sum(case((and_(current_scope, Pesanan.status == "menunggu_konfirmasi"), 1), else_=0)),
                    0,
                ).label("menunggu_konfirmasi"),
                func.coalesce(
                    func.sum(case((Pesanan.status == "selesai", 1), else_=0)),
                    0,
                ).label("selesai"),
                func.coalesce(
                    func.sum(case((Pesanan.status == "dibatalkan", 1), else_=0)),
                    0,
                ).label("dibatalkan"),
                customer_count.label("total_customer"),
                active_partner_count.label("mitra_aktif"),
                active_service_count.label("layanan_aktif"),
            )
        )
    ).one()

    m = row._mapping
    return {
        key: int(m[key] or 0)
        for key in (
            "total_order",
            "pesanan_baru",
            "sedang_diproses",
            "menunggu_konfirmasi",
            "selesai",
            "dibatalkan",
            "total_customer",
            "mitra_aktif",
            "layanan_aktif",
        )
    }

@router.get("/api/ops/admin/orders")
async def admin_orders(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    view: str = "aktif",
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    _private_no_store(response)
    page, page_size = _page_values(page, page_size, 20)

    view = _norm(view)
    conditions = []
    if view == "aktif":
        conditions.append(Pesanan.status.in_(tuple(INTERNAL_ACTIVE)))
        conditions.extend(_current_order_conditions())
    elif view in {
        "menunggu",
        "diproses",
        "ditugaskan",
        "menuju_lokasi",
        "dimulai",
        "menunggu_konfirmasi",
        "selesai",
        "dibatalkan",
    }:
        conditions.append(Pesanan.status == view)
        if view in INTERNAL_ACTIVE:
            conditions.extend(_current_order_conditions())
    elif view != "all":
        view = "aktif"
        conditions.append(Pesanan.status.in_(tuple(INTERNAL_ACTIVE)))
        conditions.extend(_current_order_conditions())

    count_stmt = select(func.count(Pesanan.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Pesanan,
            User.nama.label("pelanggan_nama"),
            User.no_hp.label("pelanggan_wa"),
            Layanan.nama.label("layanan_nama"),
            LayananVarian.nama.label("varian_nama"),
        )
        .join(User, User.id == Pesanan.user_id)
        .outerjoin(Layanan, Layanan.id == Pesanan.layanan_id)
        .outerjoin(LayananVarian, LayananVarian.id == Pesanan.varian_id)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    rows = (
        await db.execute(
            stmt.order_by(Pesanan.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    order_ids = [row[0].id for row in rows]
    assignment_map: dict[str, tuple[PenugasanMitra, Mitra | None]] = {}
    payment_map: dict[str, PaymentTransaction] = {}

    if order_ids:
        assignment_rows = (
            await db.execute(
                select(PenugasanMitra, Mitra)
                .outerjoin(Mitra, Mitra.id == PenugasanMitra.mitra_id)
                .where(
                    PenugasanMitra.pesanan_id.in_(order_ids),
                    PenugasanMitra.aktif == True,  # noqa: E712
                )
                .order_by(
                    PenugasanMitra.pesanan_id,
                    PenugasanMitra.assigned_at.desc(),
                )
            )
        ).all()
        for assignment, partner in assignment_rows:
            assignment_map.setdefault(assignment.pesanan_id, (assignment, partner))

        payment_rows = (
            await db.execute(
                select(PaymentTransaction)
                .where(PaymentTransaction.pesanan_id.in_(order_ids))
                .order_by(
                    PaymentTransaction.pesanan_id,
                    PaymentTransaction.created_at.desc(),
                )
            )
        ).scalars().all()
        for payment in payment_rows:
            payment_map.setdefault(payment.pesanan_id, payment)

    items = []
    for order, customer_name, customer_phone, service_name, variant_name in rows:
        assignment, partner = assignment_map.get(order.id, (None, None))
        items.append(
            _admin_payload_from_parts(
                order,
                customer_name,
                customer_phone,
                service_name,
                variant_name,
                assignment,
                partner,
                payment_map.get(order.id),
            )
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
        "has_more": page * page_size < int(total or 0),
        "view": view,
    }

@router.get("/api/ops/admin/orders/{order_id}")
async def admin_order_detail(
    order_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    _private_no_store(response)

    row = (
        await db.execute(
            select(
                Pesanan,
                User.nama.label("pelanggan_nama"),
                User.no_hp.label("pelanggan_wa"),
                Layanan.nama.label("layanan_nama"),
                LayananVarian.nama.label("varian_nama"),
            )
            .join(User, User.id == Pesanan.user_id)
            .outerjoin(Layanan, Layanan.id == Pesanan.layanan_id)
            .outerjoin(LayananVarian, LayananVarian.id == Pesanan.varian_id)
            .where(or_(Pesanan.id == order_id, Pesanan.kode == order_id))
            .limit(1)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    order, customer_name, customer_phone, service_name, variant_name = row
    assignment_row = (
        await db.execute(
            select(PenugasanMitra, Mitra)
            .outerjoin(Mitra, Mitra.id == PenugasanMitra.mitra_id)
            .where(
                PenugasanMitra.pesanan_id == order.id,
                PenugasanMitra.aktif == True,  # noqa: E712
            )
            .order_by(PenugasanMitra.assigned_at.desc())
            .limit(1)
        )
    ).first()
    assignment, partner = assignment_row if assignment_row else (None, None)

    payment = (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.pesanan_id == order.id)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return _admin_payload_from_parts(
        order,
        customer_name,
        customer_phone,
        service_name,
        variant_name,
        assignment,
        partner,
        payment,
    )


@router.post("/api/ops/admin/orders/{order_id}/distance")
async def admin_confirm_distance(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(
        order,
        {"menunggu", "diproses", "ditugaskan", "menuju_lokasi"},
        "Mengonfirmasi ongkos jarak",
    )

    service = await db.get(Layanan, order.layanan_id)
    if not service or _norm(service.nama) not in {"trapis", "pijat & relaksasi"}:
        raise HTTPException(409, "Ongkos jarak hanya berlaku untuk layanan Pijat & Relaksasi")

    try:
        distance_km = float(data.get("distance_km"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Jarak layanan tidak valid") from exc
    if not math.isfinite(distance_km) or distance_km < 0 or distance_km > 100:
        raise HTTPException(400, "Jarak layanan harus antara 0 dan 100 km")

    payment = await _latest_payment(db, order.id)
    if payment and _norm(payment.status) == "paid":
        raise HTTPException(409, "Ongkos jarak tidak dapat diubah setelah pembayaran selesai")

    form_data = _order_form_data(order)
    extras = form_data.get("extras") if isinstance(form_data.get("extras"), dict) else {}
    previous_policy = (
        extras.get("distance_policy")
        if isinstance(extras.get("distance_policy"), dict)
        else {}
    )
    old_surcharge = (
        _safe_nonnegative_int(extras.get("distance_surcharge"))
        if previous_policy.get("confirmed_by_admin") is True
        else 0
    )
    base_total = int(order.total_harga or 0) - old_surcharge
    if base_total <= 0:
        raise HTTPException(409, "Total dasar pesanan tidak valid")

    surcharge = _distance_surcharge(distance_km)
    order.total_harga = base_total + surcharge
    extras["distance_km"] = round(distance_km, 2)
    extras["distance_surcharge"] = surcharge
    extras["distance_policy"] = {
        "free_km": 5,
        "rate_per_km": 10000,
        "rounding": "ceil_excess",
        "confirmed_by_admin": True,
    }
    form_data["extras"] = extras
    order.form_data = json.dumps(form_data, ensure_ascii=False)
    if payment:
        payment.amount = order.total_harga

    await _history(
        db,
        order,
        admin.id,
        order.status,
        order.status,
        f"Ongkos jarak dikonfirmasi: {distance_km:.2f} km, tambahan Rp{surcharge:,}",
    )
    await _customer_notification(
        db,
        order,
        "Ongkos jarak dikonfirmasi",
        f"Jarak layanan {distance_km:.2f} km. Tambahan ongkos jarak Rp{surcharge:,}. Total pesanan telah diperbarui.",
    )
    await db.commit()
    return {
        "success": True,
        "distance_km": round(distance_km, 2),
        "distance_surcharge": surcharge,
        "total_harga": order.total_harga,
    }


# Legacy arbitrary status mutation is intentionally shadowed by this router.

# Legacy arbitrary status mutation is intentionally shadowed by this router.
@router.put("/api/admin/pesanan/{order_id}/status")
async def disable_legacy_status_mutation(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    await _find_order(db, order_id)
    raise HTTPException(
        409,
        "Perubahan status bebas dinonaktifkan. Gunakan aksi operasional BantuDulu.",
    )


@router.post("/api/ops/admin/orders/{order_id}/accept")
async def admin_accept_order(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"menunggu"}, "Menerima pesanan")

    old = order.status
    order.status = "diproses"
    await _history(db, order, admin.id, old, order.status, "Pesanan diterima Admin BantuDulu")
    await _customer_notification(
        db,
        order,
        "Pesanan diterima BantuDulu",
        "Pesanan Anda sudah kami terima dan sedang kami siapkan.",
    )
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/assign")
async def admin_assign_partner(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"diproses", "ditugaskan"}, "Menugaskan mitra")

    partner = await db.get(Mitra, str(data.get("mitra_id") or ""))
    if not partner or not partner.aktif or partner.status == "nonaktif":
        raise HTTPException(404, "Mitra tidak tersedia")

    linked = (
        await db.execute(
            select(MitraLayanan).where(
                MitraLayanan.mitra_id == partner.id,
                MitraLayanan.layanan_id == order.layanan_id,
                MitraLayanan.aktif == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not linked:
        raise HTTPException(409, "Mitra belum terdaftar untuk layanan pesanan ini")

    busy = (
        await db.execute(
            select(PenugasanMitra).where(
                PenugasanMitra.mitra_id == partner.id,
                PenugasanMitra.aktif == True,  # noqa: E712
            )
        )
    ).scalars().first()
    if busy and busy.pesanan_id != order.id:
        raise HTTPException(409, "Mitra masih menangani pesanan lain")

    current = await _active_assignment(db, order.id)
    if current:
        current.aktif = False
        current.status = "diganti"

    old = order.status
    order.status = "ditugaskan"
    partner.status = "sibuk"
    db.add(
        PenugasanMitra(
            pesanan_id=order.id,
            mitra_id=partner.id,
            assigned_by_user_id=admin.id,
            status="ditugaskan",
            aktif=True,
        )
    )
    await _history(
        db,
        order,
        admin.id,
        old,
        order.status,
        f"Admin menugaskan mitra {partner.nama}",
    )
    await db.commit()
    return {"success": True, "status": order.status, "mitra_id": partner.id}


@router.post("/api/ops/admin/orders/{order_id}/partner-accept")
async def admin_partner_accept(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"ditugaskan"}, "Konfirmasi mitra")

    assignment = await _active_assignment(db, order.id)
    if not assignment:
        raise HTTPException(409, "Belum ada mitra aktif untuk pesanan ini")
    assignment.status = "diterima"
    assignment.accepted_at = _utcnow_db()
    await _history(
        db,
        order,
        admin.id,
        order.status,
        order.status,
        "Admin mencatat mitra menerima penugasan",
    )
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/partner-reject")
async def admin_partner_reject(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"ditugaskan"}, "Penolakan mitra")

    assignment = await _active_assignment(db, order.id)
    if not assignment:
        raise HTTPException(409, "Belum ada mitra aktif untuk pesanan ini")
    partner = await db.get(Mitra, assignment.mitra_id)
    assignment.status = "ditolak"
    assignment.aktif = False
    if partner:
        partner.status = "tersedia"

    old = order.status
    order.status = "diproses"
    reason = str(data.get("reason") or "Mitra tidak dapat menerima tugas").strip()[:500]
    await _history(db, order, admin.id, old, order.status, f"Mitra ditolak/diganti: {reason}")
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/on-the-way")
async def admin_on_the_way(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"ditugaskan"}, "Memulai perjalanan")

    assignment = await _active_assignment(db, order.id)
    if not assignment:
        raise HTTPException(409, "Belum ada mitra aktif untuk pesanan ini")
    if assignment.status != "diterima":
        raise HTTPException(409, "Admin harus mencatat mitra menerima tugas terlebih dahulu")

    old = order.status
    order.status = "menuju_lokasi"
    assignment.status = "menuju_lokasi"
    await _history(db, order, admin.id, old, order.status, "Tim BantuDulu menuju lokasi")
    await _customer_notification(
        db,
        order,
        "Tim BantuDulu menuju lokasi",
        "Tim BantuDulu sedang menuju lokasi Anda.",
    )
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/work-started")
async def admin_work_started(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"menuju_lokasi"}, "Memulai pekerjaan")

    assignment = await _active_assignment(db, order.id)
    if not assignment:
        raise HTTPException(409, "Penugasan aktif tidak ditemukan")
    old = order.status
    order.status = "dimulai"
    assignment.status = "dikerjakan"
    await _history(db, order, admin.id, old, order.status, "Pekerjaan dimulai")
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/work-reported")
async def admin_work_reported(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"dimulai"}, "Melaporkan pekerjaan selesai")

    assignment = await _active_assignment(db, order.id)
    if not assignment:
        raise HTTPException(409, "Penugasan aktif tidak ditemukan")
    old = order.status
    order.status = "menunggu_konfirmasi"
    assignment.status = "menunggu_konfirmasi"
    await _history(
        db,
        order,
        admin.id,
        old,
        order.status,
        "Pekerjaan dilaporkan selesai, menunggu konfirmasi Admin",
    )
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/complete")
async def admin_complete_order(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    _assert_status(order, {"menunggu_konfirmasi"}, "Menyelesaikan pesanan")

    if data.get("work_confirmed") is not True:
        raise HTTPException(400, "Admin harus mengonfirmasi pekerjaan telah selesai")
    if data.get("payment_confirmed") is not True:
        raise HTTPException(400, "Admin harus mengonfirmasi pembayaran telah selesai")

    method = _payment_method(order)
    payment = await _latest_payment(db, order.id)
    now = _utcnow_db()
    if not payment:
        payment = PaymentTransaction(
            pesanan_id=order.id,
            method=method,
            status="paid",
            amount=order.total_harga,
            provider="manual",
            paid_at=now,
        )
        db.add(payment)
    else:
        payment.status = "paid"
        payment.paid_at = now

    assignment = await _active_assignment(db, order.id)
    partner = await db.get(Mitra, assignment.mitra_id) if assignment else None
    if assignment:
        assignment.status = "selesai"
        assignment.aktif = False
        assignment.completed_at = now
    if partner:
        partner.status = "tersedia"
        partner.total_jobs = int(partner.total_jobs or 0) + 1

    old = order.status
    order.status = "selesai"
    await _history(
        db,
        order,
        admin.id,
        old,
        order.status,
        "Admin mengonfirmasi pekerjaan dan pembayaran selesai",
    )
    await _customer_notification(
        db,
        order,
        "Pesanan selesai",
        "Pesanan Anda telah diselesaikan oleh BantuDulu.",
    )
    await db.commit()
    return {"success": True, "status": order.status}


@router.post("/api/ops/admin/orders/{order_id}/cancel")
async def admin_cancel_order(
    order_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = await _admin(request, db)
    order = await _find_order(db, order_id)
    if _is_legacy_order(order):
        raise HTTPException(409, "Pesanan aktif lama/arsip tidak dapat diubah melalui flow Operational V1.")
    if order.status in TERMINAL:
        raise HTTPException(409, "Pesanan yang sudah final tidak dapat dibatalkan")

    reason = str(data.get("reason") or "").strip()
    if len(reason) < 3:
        raise HTTPException(400, "Alasan pembatalan wajib diisi")

    assignment = await _active_assignment(db, order.id)
    if assignment:
        assignment.status = "dibatalkan"
        assignment.aktif = False
        partner = await db.get(Mitra, assignment.mitra_id)
        if partner:
            partner.status = "tersedia"

    old = order.status
    order.status = "dibatalkan"
    await _history(db, order, admin.id, old, order.status, f"Dibatalkan Admin: {reason[:500]}")
    await _customer_notification(
        db,
        order,
        "Pesanan dibatalkan",
        "Pesanan Anda dibatalkan oleh BantuDulu. Hubungi Admin bila perlu bantuan.",
    )
    await db.commit()
    return {"success": True, "status": order.status}


# ── Mitra: manual, Admin-controlled ───────────────────────────────────────────

@router.get("/api/ops/admin/partners")
async def admin_partners(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    partners = (await db.execute(select(Mitra).order_by(Mitra.nama))).scalars().all()
    out = []
    for partner in partners:
        links = (
            await db.execute(
                select(MitraLayanan).where(
                    MitraLayanan.mitra_id == partner.id,
                    MitraLayanan.aktif == True,  # noqa: E712
                )
            )
        ).scalars().all()
        services = []
        for link in links:
            service = await db.get(Layanan, link.layanan_id)
            if service:
                services.append({"id": service.id, "nama": service.nama})
        active_job = (
            await db.execute(
                select(PenugasanMitra).where(
                    PenugasanMitra.mitra_id == partner.id,
                    PenugasanMitra.aktif == True,  # noqa: E712
                )
            )
        ).scalars().first()
        out.append(
            {
                "id": partner.id,
                "nama": partner.nama,
                "no_hp": partner.no_hp,
                "email": partner.email or "",
                "status": partner.status,
                "aktif": partner.aktif,
                "rating": partner.rating,
                "total_jobs": partner.total_jobs,
                "services": services,
                "sedang_bertugas": bool(active_job),
            }
        )
    return out


@router.post("/api/ops/admin/partners")
async def admin_create_partner(
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    nama = str(data.get("nama") or "").strip()
    no_hp = _phone(str(data.get("no_hp") or ""))
    email = str(data.get("email") or "").strip().lower() or None
    service_ids = [str(x) for x in (data.get("service_ids") or []) if str(x).strip()]

    if not nama or len(no_hp) < 8:
        raise HTTPException(400, "Nama dan nomor HP mitra wajib diisi")
    if not service_ids:
        raise HTTPException(400, "Pilih minimal satu layanan untuk mitra")

    duplicate = (
        await db.execute(select(Mitra).where(Mitra.no_hp == no_hp))
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(409, "Nomor HP mitra sudah terdaftar")

    partner = Mitra(
        nama=nama[:120],
        no_hp=no_hp[:20],
        email=email[:120] if email else None,
        status="tersedia",
        aktif=True,
    )
    db.add(partner)
    await db.flush()

    valid_count = 0
    for service_id in dict.fromkeys(service_ids[:100]):
        service = await db.get(Layanan, service_id)
        if service and service.aktif:
            db.add(
                MitraLayanan(
                    key=f"{partner.id}:{service.id}",
                    mitra_id=partner.id,
                    layanan_id=service.id,
                    aktif=True,
                )
            )
            valid_count += 1
    if valid_count == 0:
        await db.rollback()
        raise HTTPException(400, "Layanan mitra tidak valid")

    await db.commit()
    return {"success": True, "id": partner.id}


@router.put("/api/ops/admin/partners/{partner_id}")
async def admin_update_partner(
    partner_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    partner = await db.get(Mitra, partner_id)
    if not partner:
        raise HTTPException(404, "Mitra tidak ditemukan")

    if "nama" in data:
        nama = str(data.get("nama") or "").strip()
        if nama:
            partner.nama = nama[:120]
    if "no_hp" in data:
        no_hp = _phone(str(data.get("no_hp") or ""))
        if len(no_hp) < 8:
            raise HTTPException(400, "Nomor HP tidak valid")
        partner.no_hp = no_hp[:20]
    if "email" in data:
        email = str(data.get("email") or "").strip().lower()
        partner.email = email[:120] or None
    if "aktif" in data:
        new_active = bool(data.get("aktif"))
        if not new_active:
            active_job = (
                await db.execute(
                    select(PenugasanMitra).where(
                        PenugasanMitra.mitra_id == partner.id,
                        PenugasanMitra.aktif == True,  # noqa: E712
                    )
                )
            ).scalars().first()
            if active_job:
                raise HTTPException(409, "Mitra yang sedang bertugas tidak dapat dinonaktifkan")
        partner.aktif = new_active
        if not partner.aktif:
            partner.status = "nonaktif"
        elif partner.status == "nonaktif":
            partner.status = "tersedia"
    if "status" in data:
        status = str(data.get("status") or "").strip().lower()
        if status not in {"tersedia", "sibuk", "nonaktif"}:
            raise HTTPException(400, "Status mitra tidak valid")
        partner.status = status
        partner.aktif = status != "nonaktif"

    if "service_ids" in data:
        service_ids = {str(x) for x in (data.get("service_ids") or []) if str(x).strip()}
        current = (
            await db.execute(select(MitraLayanan).where(MitraLayanan.mitra_id == partner.id))
        ).scalars().all()
        by_service = {row.layanan_id: row for row in current}
        for row in current:
            row.aktif = row.layanan_id in service_ids
        for service_id in service_ids:
            service = await db.get(Layanan, service_id)
            if service and service.aktif and service_id not in by_service:
                db.add(
                    MitraLayanan(
                        key=f"{partner.id}:{service.id}",
                        mitra_id=partner.id,
                        layanan_id=service.id,
                        aktif=True,
                    )
                )

    await db.commit()
    return {"success": True}


# ── Real catalog: no hard-coded admin cards, no archive/zero-price variants ───

async def _catalog_payload(db: AsyncSession, include_inactive: bool) -> list[dict]:
    stmt = select(Layanan).order_by(Layanan.nama)
    if not include_inactive:
        stmt = stmt.where(Layanan.aktif == True)  # noqa: E712
    services = (await db.execute(stmt)).scalars().all()
    out = []
    for service in services:
        category = await db.get(Kategori, service.kategori_id)
        variants = (
            await db.execute(
                select(LayananVarian)
                .where(LayananVarian.layanan_id == service.id)
                .order_by(LayananVarian.harga, LayananVarian.nama)
            )
        ).scalars().all()
        variants = [
            v for v in variants
            if int(v.harga or 0) > 0 and "arsip" not in _norm(v.nama)
        ]
        out.append(
            {
                "id": service.id,
                "nama": service.nama,
                "deskripsi": service.deskripsi,
                "tipe_hitung": service.tipe_hitung,
                "aktif": service.aktif,
                "kategori": category.nama if category else "",
                "kategori_id": service.kategori_id,
                "variants": [
                    {
                        "id": v.id,
                        "nama": v.nama,
                        "harga": v.harga,
                        "deskripsi": v.deskripsi or "",
                    }
                    for v in variants
                ],
            }
        )
    return out


@router.get("/api/ops/admin/catalog")
async def admin_catalog(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    return await _catalog_payload(db, include_inactive=True)


# Shadow compatibility catalog reads so archive Rp0 variants never reach live UI.
@router.get("/api/layanan")
async def safe_catalog_list(db: AsyncSession = Depends(get_db)):
    rows = await _catalog_payload(db, include_inactive=False)
    return [
        {
            "id": row["id"],
            "kategori_id": row["kategori_id"],
            "nama": row["nama"],
            "deskripsi": row["deskripsi"],
            "jenis_layanan": "",
            "tipe_hitung": row["tipe_hitung"],
            "gambar_url": None,
            "harga_min": min((v["harga"] for v in row["variants"]), default=0),
        }
        for row in rows
        if row["variants"]
    ]


@router.get("/api/layanan/{layanan_id}")
async def safe_catalog_detail(
    layanan_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = await db.get(Layanan, layanan_id)
    if not service or not service.aktif:
        raise HTTPException(404, "Layanan tidak ditemukan")

    category = await db.get(Kategori, service.kategori_id)
    variants = (
        await db.execute(
            select(LayananVarian).where(LayananVarian.layanan_id == service.id)
        )
    ).scalars().all()
    variants = [
        v for v in variants
        if int(v.harga or 0) > 0 and "arsip" not in _norm(v.nama)
    ]
    fields = (
        await db.execute(
            select(FormField)
            .where(FormField.layanan_id == service.id)
            .order_by(FormField.urutan)
        )
    ).scalars().all()

    return {
        "layanan": {
            "id": service.id,
            "nama": service.nama,
            "deskripsi": service.deskripsi,
            "catatan": service.catatan,
            "jenis_layanan": service.jenis_layanan,
            "tipe_hitung": service.tipe_hitung,
            "kategori": {
                "nama": category.nama if category else "",
                "icon": category.icon if category else "",
                "warna": category.warna if category else "#28758b",
            },
        },
        "varian": [
            {"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi}
            for v in variants
        ],
        "form_fields": [
            {
                "id": f.id,
                "label": f.label,
                "field_type": f.field_type,
                "options": json.loads(f.options) if f.options else [],
                "required": f.required,
                "harga_tambahan": f.harga_tambahan,
            }
            for f in fields
        ],
    }
