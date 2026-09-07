from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_from_request
from app.config import MARKETPLACE_SCHEMA_ENABLED
from app.database import get_db
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


def _payment_method(order: Pesanan) -> str:
    try:
        data = json.loads(order.form_data or "{}") or {}
        return str(data.get("metode_pembayaran") or "cod").strip().lower()
    except Exception:
        return "cod"


def _is_legacy_order(order: Pesanan) -> bool:
    # Imported/legacy rows can miss fields that current V1 requires.
    return (
        not str(order.alamat or "").strip()
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


async def _order_admin_payload(db: AsyncSession, order: Pesanan) -> dict:
    owner = await db.get(User, order.user_id)
    service = await db.get(Layanan, order.layanan_id)
    variant = await db.get(LayananVarian, order.varian_id)
    assignment = await _active_assignment(db, order.id)
    partner = await db.get(Mitra, assignment.mitra_id) if assignment else None
    payment = await _latest_payment(db, order.id)
    return {
        "id": order.id,
        "kode": order.kode,
        "status": order.status,
        "pelanggan_nama": owner.nama if owner else "-",
        "pelanggan_wa": owner.no_hp if owner else "",
        "layanan_id": order.layanan_id,
        "layanan_nama": service.nama if service else "Pesanan",
        "varian_nama": variant.nama if variant else "",
        "alamat": order.alamat,
        "jadwal": order.jadwal,
        "jam": order.jam,
        "durasi": order.durasi,
        "catatan": order.catatan or "",
        "total_harga": order.total_harga,
        "metode_pembayaran": payment.method if payment else _payment_method(order),
        "status_pembayaran": payment.status if payment else "belum_tercatat",
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
        "created_at": order.created_at.isoformat(),
    }


# ── Customer-safe order tracking ──────────────────────────────────────────────

@router.get("/api/ops/customer/orders")
async def customer_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    rows = (
        await db.execute(
            select(Pesanan)
            .where(Pesanan.user_id == user.id)
            .order_by(Pesanan.created_at.desc())
        )
    ).scalars().all()

    out = []
    for order in rows:
        service = await db.get(Layanan, order.layanan_id)
        variant = await db.get(LayananVarian, order.varian_id)
        out.append(
            {
                "id": order.id,
                "kode": order.kode,
                "status": _customer_public_status(order),
                "layanan_nama": service.nama if service else "Pesanan",
                "varian_nama": variant.nama if variant else "",
                "jadwal": order.jadwal,
                "jam": order.jam,
                "total_harga": order.total_harga,
                "is_legacy": _is_legacy_order(order),
                "created_at": order.created_at.isoformat(),
            }
        )
    return out


@router.get("/api/ops/customer/orders/{order_id}")
async def customer_order_detail(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    order = await _find_order(db, order_id)
    if order.user_id != user.id:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    service = await db.get(Layanan, order.layanan_id)
    variant = await db.get(LayananVarian, order.varian_id)
    return {
        "id": order.id,
        "kode": order.kode,
        "status": _customer_public_status(order),
        "layanan_nama": service.nama if service else "Pesanan",
        "varian_nama": variant.nama if variant else "",
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

@router.get("/api/ops/admin/summary")
async def admin_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)

    orders = (await db.execute(select(Pesanan))).scalars().all()
    customers = (
        await db.execute(select(func.count(User.id)).where(User.role == "CUSTOMER"))
    ).scalar_one()
    active_partners = (
        await db.execute(
            select(func.count(Mitra.id)).where(Mitra.aktif == True)  # noqa: E712
        )
    ).scalar_one()
    active_services = (
        await db.execute(
            select(func.count(Layanan.id)).where(Layanan.aktif == True)  # noqa: E712
        )
    ).scalar_one()

    return {
        "total_order": len(orders),
        "pesanan_baru": sum(o.status == "menunggu" for o in orders),
        "sedang_diproses": sum(o.status in {"diproses", "ditugaskan", "menuju_lokasi", "dimulai"} for o in orders),
        "menunggu_konfirmasi": sum(o.status == "menunggu_konfirmasi" for o in orders),
        "selesai": sum(o.status == "selesai" for o in orders),
        "dibatalkan": sum(o.status == "dibatalkan" for o in orders),
        "total_customer": int(customers or 0),
        "mitra_aktif": int(active_partners or 0),
        "layanan_aktif": int(active_services or 0),
    }


@router.get("/api/ops/admin/orders")
async def admin_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    rows = (
        await db.execute(select(Pesanan).order_by(Pesanan.created_at.desc()))
    ).scalars().all()
    return [await _order_admin_payload(db, row) for row in rows]


@router.get("/api/ops/admin/orders/{order_id}")
async def admin_order_detail(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _admin(request, db)
    order = await _find_order(db, order_id)
    return await _order_admin_payload(db, order)


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
    assignment.accepted_at = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
