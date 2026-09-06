import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_from_request
from app.config import MARKETPLACE_SCHEMA_ENABLED
from app.database import get_db
from app.models import (
    FormField,
    Kategori,
    Layanan,
    LayananVarian,
    OrderStatusHistory,
    Pesanan,
    User,
)

router = APIRouter(prefix="/api", tags=["api-compat"])


async def require_user_api(request: Request, db: AsyncSession) -> User:
    auth = get_user_from_request(request)
    if not auth or not auth.get("id"):
        raise HTTPException(401, "Silakan login terlebih dahulu")
    user = await db.get(User, auth["id"])
    if not user:
        raise HTTPException(401, "Session tidak valid")
    return user


async def require_admin_api(request: Request, db: AsyncSession) -> User:
    user = await require_user_api(request, db)
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya admin.")
    return user


# ── Public catalog read APIs ──

@router.get("/kategori")
async def get_kategori(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Kategori).order_by(Kategori.urutan))
    return [
        {"id": k.id, "nama": k.nama, "icon": k.icon, "slug": k.slug, "warna": k.warna}
        for k in result.scalars().all()
    ]


@router.get("/layanan")
async def get_layanan(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Layanan).where(Layanan.aktif == True))  # noqa: E712
    data = []
    for layanan in result.scalars().all():
        varian_res = await db.execute(
            select(LayananVarian.harga)
            .where(LayananVarian.layanan_id == layanan.id)
            .order_by(LayananVarian.harga)
            .limit(1)
        )
        data.append(
            {
                "id": layanan.id,
                "kategori_id": layanan.kategori_id,
                "nama": layanan.nama,
                "deskripsi": layanan.deskripsi,
                "jenis_layanan": layanan.jenis_layanan,
                "tipe_hitung": layanan.tipe_hitung,
                "gambar_url": layanan.gambar_url,
                "harga_min": varian_res.scalar() or 0,
            }
        )
    return data


@router.get("/layanan/{layanan_id}")
async def get_layanan_detail(layanan_id: str, db: AsyncSession = Depends(get_db)):
    layanan = (
        await db.execute(select(Layanan).where(Layanan.id == layanan_id))
    ).scalar_one_or_none()
    if not layanan:
        raise HTTPException(404, "Layanan tidak ditemukan")

    varian = (
        await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == layanan_id))
    ).scalars().all()
    fields = (
        await db.execute(
            select(FormField)
            .where(FormField.layanan_id == layanan_id)
            .order_by(FormField.urutan)
        )
    ).scalars().all()
    kategori = (
        await db.execute(select(Kategori).where(Kategori.id == layanan.kategori_id))
    ).scalar_one()

    return {
        "layanan": {
            "id": layanan.id,
            "nama": layanan.nama,
            "deskripsi": layanan.deskripsi,
            "catatan": layanan.catatan,
            "jenis_layanan": layanan.jenis_layanan,
            "tipe_hitung": layanan.tipe_hitung,
            "kategori": {
                "nama": kategori.nama,
                "icon": kategori.icon,
                "warna": kategori.warna,
            },
        },
        "varian": [
            {"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi}
            for v in varian
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


# ── Compatibility order reads: authenticated and ownership-scoped ──

@router.get("/pesanan")
async def get_pesanan(
    request: Request,
    user_id: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    current = await require_user_api(request, db)
    stmt = select(Pesanan)

    if current.role == "ADMIN":
        if user_id:
            stmt = stmt.where(Pesanan.user_id == user_id)
    else:
        stmt = stmt.where(Pesanan.user_id == current.id)

    if status:
        stmt = stmt.where(Pesanan.status == status)

    stmt = stmt.order_by(Pesanan.created_at.desc())
    pesanan = (await db.execute(stmt)).scalars().all()

    data = []
    for p in pesanan:
        layanan = await db.get(Layanan, p.layanan_id)
        varian = await db.get(LayananVarian, p.varian_id)
        owner = await db.get(User, p.user_id)
        data.append(
            {
                "id": p.id,
                "kode": p.kode,
                "status": p.status,
                "alamat": p.alamat,
                "tanggal": p.jadwal,
                "jadwal": p.jadwal,
                "jam": p.jam,
                "durasi": p.durasi,
                "total_harga": p.total_harga,
                "harga": p.total_harga,
                "catatan": p.catatan,
                "form_data": p.form_data,
                "no_wa": owner.no_hp if owner else None,
                "wa_kontak": owner.no_hp if owner else None,
                "layanan_nama": layanan.nama if layanan else None,
                "varian_nama": varian.nama if varian else None,
                "created_at": p.created_at.isoformat(),
            }
        )
    return data


@router.get("/pesanan/aktif")
async def get_pesanan_aktif(request: Request, db: AsyncSession = Depends(get_db)):
    current = await require_user_api(request, db)
    active_statuses = ["menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai"]
    stmt = (
        select(Pesanan)
        .where(Pesanan.user_id == current.id)
        .where(Pesanan.status.in_(active_statuses))
        .order_by(Pesanan.created_at.desc())
        .limit(5)
    )
    pesanan = (await db.execute(stmt)).scalars().all()
    data = []
    for p in pesanan:
        layanan = await db.get(Layanan, p.layanan_id)
        data.append(
            {
                "id": p.id,
                "kode": p.kode,
                "status": p.status,
                "alamat": p.alamat,
                "total_harga": p.total_harga,
                "layanan_nama": layanan.nama if layanan else "Pesanan",
                "created_at": p.created_at.isoformat(),
            }
        )
    return {"data": data}


@router.get("/pesanan/{pesanan_id}")
async def get_pesanan_detail(
    request: Request,
    pesanan_id: str,
    db: AsyncSession = Depends(get_db),
):
    current = await require_user_api(request, db)
    p = (
        await db.execute(
            select(Pesanan).where(
                or_(Pesanan.id == pesanan_id, Pesanan.kode == pesanan_id)
            )
        )
    ).scalar_one_or_none()

    if not p:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    if current.role != "ADMIN" and p.user_id != current.id:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    layanan = await db.get(Layanan, p.layanan_id)
    varian = await db.get(LayananVarian, p.varian_id)
    owner = await db.get(User, p.user_id)

    form_data_obj = {}
    if p.form_data:
        try:
            form_data_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
        except (json.JSONDecodeError, TypeError):
            form_data_obj = {}

    return {
        "id": p.id,
        "kode": p.kode,
        "status": p.status,
        "alamat": p.alamat,
        "tanggal": p.jadwal,
        "jadwal": p.jadwal,
        "jam": p.jam,
        "durasi": p.durasi,
        "total_harga": p.total_harga,
        "harga": p.total_harga,
        "catatan": p.catatan,
        "form_data": p.form_data,
        "metode_pembayaran": form_data_obj.get("metode_pembayaran") or "cod",
        "created_at": p.created_at.isoformat(),
        "layanan_nama": layanan.nama if layanan else None,
        "varian_nama": varian.nama if varian else None,
        "pelanggan_nama": owner.nama if owner else None,
        "no_wa": owner.no_hp if owner else None,
        "wa_kontak": owner.no_hp if owner else None,
    }


# ── Admin APIs ──

@router.get("/admin/pesanan")
async def get_all_pesanan(
    request: Request,
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    await require_admin_api(request, db)
    stmt = select(Pesanan)
    if status:
        stmt = stmt.where(Pesanan.status == status)
    stmt = stmt.order_by(Pesanan.created_at.desc())

    data = []
    for p in (await db.execute(stmt)).scalars().all():
        owner = await db.get(User, p.user_id)
        layanan = await db.get(Layanan, p.layanan_id)
        data.append(
            {
                "id": p.id,
                "kode": p.kode,
                "status": p.status,
                "pelanggan": owner.nama if owner else "Unknown",
                "layanan": layanan.nama if layanan else "Unknown",
                "total_harga": p.total_harga,
                "jadwal": p.jadwal,
                "created_at": p.created_at.isoformat(),
                "form_data": p.form_data,
            }
        )
    return data


@router.get("/admin/kelola-pesanan")
async def get_kelola_pesanan(request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin_api(request, db)
    unresolved = {"menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai"}
    stmt = (
        select(Pesanan)
        .where(Pesanan.status.in_(unresolved))
        .order_by(Pesanan.created_at.desc())
    )

    data = []
    for p in (await db.execute(stmt)).scalars().all():
        owner = await db.get(User, p.user_id)
        layanan = await db.get(Layanan, p.layanan_id)
        varian = await db.get(LayananVarian, p.varian_id)

        form_data_obj = {}
        if p.form_data:
            try:
                form_data_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
            except (json.JSONDecodeError, TypeError):
                form_data_obj = {}

        data.append(
            {
                "id": p.id,
                "kode": p.kode,
                "status": p.status,
                "pelanggan_nama": owner.nama if owner else "Unknown",
                "pelanggan_wa": owner.no_hp if owner else None,
                "alamat": p.alamat,
                "catatan": p.catatan,
                "jadwal": p.jadwal,
                "jam": p.jam,
                "durasi": p.durasi,
                "layanan_nama": layanan.nama if layanan else None,
                "varian_nama": varian.nama if varian else None,
                "total_harga": p.total_harga,
                "metode_pembayaran": form_data_obj.get("metode_pembayaran") or "cod",
                "form_data": {
                    k: v for k, v in form_data_obj.items() if k != "metode_pembayaran"
                } or None,
                "created_at": p.created_at.isoformat(),
            }
        )
    return data


@router.put("/admin/pesanan/{pesanan_id}/status")
async def update_pesanan_status(
    request: Request,
    pesanan_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    admin = await require_admin_api(request, db)
    status_baru = str(body.get("status") or "").lower().strip()
    valid_status = {
        "menunggu",
        "diproses",
        "ditugaskan",
        "menuju_lokasi",
        "dimulai",
        "selesai",
        "dibatalkan",
    }
    if status_baru not in valid_status:
        raise HTTPException(400, "Status tidak valid")

    pesanan = (
        await db.execute(
            select(Pesanan).where(
                or_(Pesanan.id == pesanan_id, Pesanan.kode == pesanan_id)
            )
        )
    ).scalar_one_or_none()
    if not pesanan:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    old_status = pesanan.status
    pesanan.status = status_baru

    if MARKETPLACE_SCHEMA_ENABLED:
        db.add(
            OrderStatusHistory(
                pesanan_id=pesanan.id,
                status_from=old_status,
                status_to=status_baru,
                changed_by_user_id=admin.id,
                catatan="Status diperbarui admin",
            )
        )

    await db.commit()
    await db.refresh(pesanan)
    return {"success": True, "kode": pesanan.kode, "status": pesanan.status}


@router.get("/admin/stats")
async def get_admin_stats(request: Request, db: AsyncSession = Depends(get_db)):
    await require_admin_api(request, db)

    users = await db.execute(select(User))
    total_customer = sum(1 for u in users.scalars().all() if u.role == "CUSTOMER")

    all_pesanan = (await db.execute(select(Pesanan))).scalars().all()
    today_utc = datetime.now(timezone.utc).date()

    total_layanan = len(
        (
            await db.execute(select(Layanan).where(Layanan.aktif == True))  # noqa: E712
        ).scalars().all()
    )

    return {
        "total_customer": total_customer,
        "total_order": len(all_pesanan),
        "today_order": sum(1 for p in all_pesanan if p.created_at.date() == today_utc),
        "pending_order": sum(1 for p in all_pesanan if p.status == "menunggu"),
        "total_layanan": total_layanan,
    }
