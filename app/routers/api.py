import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Kategori, Layanan, LayananVarian, Pesanan, FormField, User

router = APIRouter(prefix="/api", tags=["api"])

# ── Kategori ──

@router.get("/kategori")
async def get_kategori(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Kategori).order_by(Kategori.urutan))
    kat = result.scalars().all()
    return [{"id": k.id, "nama": k.nama, "icon": k.icon, "slug": k.slug, "warna": k.warna} for k in kat]

# ── Layanan ──

@router.get("/layanan")
async def get_layanan(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Layanan).where(Layanan.aktif == True))
    layanan = result.scalars().all()
    data = []
    for l in layanan:
        varian_res = await db.execute(
            select(LayananVarian.harga).where(LayananVarian.layanan_id == l.id).order_by(LayananVarian.harga).limit(1)
        )
        min_price = varian_res.scalar() or 0
        data.append({
            "id": l.id,
            "kategori_id": l.kategori_id,
            "nama": l.nama,
            "deskripsi": l.deskripsi,
            "jenis_layanan": l.jenis_layanan,
            "tipe_hitung": l.tipe_hitung,
            "gambar_url": l.gambar_url,
            "harga_min": min_price,
        })
    return data

@router.get("/layanan/{layanan_id}")
async def get_layanan_detail(layanan_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Layanan).where(Layanan.id == layanan_id))
    layanan = result.scalar_one_or_none()
    if not layanan:
        raise HTTPException(404, "Layanan tidak ditemukan")

    # Get varian
    varian_result = await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == layanan_id))
    varian = varian_result.scalars().all()

    # Get form fields
    fields_result = await db.execute(select(FormField).where(FormField.layanan_id == layanan_id).order_by(FormField.urutan))
    fields = fields_result.scalars().all()

    # Get kategori
    kat_result = await db.execute(select(Kategori).where(Kategori.id == layanan.kategori_id))
    kat = kat_result.scalar_one()

    return {
        "layanan": {
            "id": layanan.id,
            "nama": layanan.nama,
            "deskripsi": layanan.deskripsi,
            "catatan": layanan.catatan,
            "jenis_layanan": layanan.jenis_layanan,
            "tipe_hitung": layanan.tipe_hitung,
            "kategori": {"nama": kat.nama, "icon": kat.icon, "warna": kat.warna},
        },
        "varian": [{"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi} for v in varian],
        "form_fields": [{
            "id": f.id, "label": f.label, "field_type": f.field_type,
            "options": json.loads(f.options) if f.options else [], "required": f.required,
            "harga_tambahan": f.harga_tambahan
        } for f in fields],
    }

# ── Pesanan ──

@router.get("/pesanan")
async def get_pesanan(user_id: str = Query(None), status: str = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(Pesanan)
    if user_id:
        stmt = stmt.where(Pesanan.user_id == user_id)
    if status:
        stmt = stmt.where(Pesanan.status == status)
    stmt = stmt.order_by(Pesanan.created_at.desc())
    result = await db.execute(stmt)
    pesanan = result.scalars().all()
    data = []
    for p in pesanan:
        l = await db.get(Layanan, p.layanan_id)
        v = await db.get(LayananVarian, p.varian_id)
        u = await db.get(User, p.user_id)
        data.append({
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
            "no_wa": u.no_hp if u else None,
            "wa_kontak": u.no_hp if u else None,
            "layanan_nama": l.nama if l else None,
            "varian_nama": v.nama if v else None,
            "created_at": p.created_at.isoformat(),
        })
    return data

@router.get("/pesanan/aktif")
async def get_pesanan_aktif(request: Request, db: AsyncSession = Depends(get_db)):
    from app.auth import get_user_from_request
    user = get_user_from_request(request)
    if not user:
        return []
    user_id = user.get("id")
    if not user_id:
        return []

    active_statuses = ["menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai"]
    stmt = (
        select(Pesanan)
        .where(Pesanan.user_id == user_id)
        .where(Pesanan.status.in_(active_statuses))
        .order_by(Pesanan.created_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    pesanan = result.scalars().all()
    data = []
    for p in pesanan:
        l = await db.get(Layanan, p.layanan_id)
        data.append({
            "id": p.id,
            "kode": p.kode,
            "status": p.status,
            "alamat": p.alamat,
            "total_harga": p.total_harga,
            "layanan_nama": l.nama if l else "Pesanan",
            "created_at": p.created_at.isoformat(),
        })
    return {"data": data}

@router.get("/pesanan/{pesanan_id}")
async def get_pesanan_detail(pesanan_id: str, db: AsyncSession = Depends(get_db)):
    import logging
    logging.getLogger('bantudulu').info(f'get_pesanan_detail called with: {pesanan_id}')
    # Cari berdasarkan ID atau Kode
    result = await db.execute(
        select(Pesanan).where(
            (Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, f"Pesanan tidak ditemukan (id/kode: {pesanan_id})")
    l = await db.get(Layanan, p.layanan_id)
    v = await db.get(LayananVarian, p.varian_id)
    u = await db.get(User, p.user_id)

    # ── Parse form_data jika ada ──
    form_data_obj = {}
    if p.form_data:
        try:
            form_data_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
        except (json.JSONDecodeError, TypeError):
            form_data_obj = {}
    metode_pembayaran = form_data_obj.get("metode_pembayaran") or "cod"

    return {
        "id": p.id,
        "kode": p.kode,
        "status": p.status,
        "alamat": p.alamat,
        "tanggal": p.jadwal,  # alias untuk frontend
        "jadwal": p.jadwal,
        "jam": p.jam,
        "durasi": p.durasi,
        "total_harga": p.total_harga,
        "harga": p.total_harga,
        "catatan": p.catatan,
        "form_data": p.form_data,
        "metode_pembayaran": metode_pembayaran,
        "created_at": p.created_at.isoformat(),
        "layanan_nama": l.nama if l else None,
        "varian_nama": v.nama if v else None,
        "pelanggan_nama": u.nama if u else None,
        "no_wa": u.no_hp if u else None,
        "wa_kontak": u.no_hp if u else None,
    }

# ── Admin API auth helper ──
def require_admin_api(request: Request):
    user = request.state.user
    if not user or user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya admin.")
    return user

@router.get("/admin/pesanan")
async def get_all_pesanan(request: Request, status: str = Query(None), db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    stmt = select(Pesanan)
    if status:
        stmt = stmt.where(Pesanan.status == status)
    stmt = stmt.order_by(Pesanan.created_at.desc())
    result = await db.execute(stmt)
    pesanan = result.scalars().all()
    data = []
    for p in pesanan:
        u = await db.get(User, p.user_id)
        l = await db.get(Layanan, p.layanan_id)
        data.append({
            "id": p.id,
            "kode": p.kode,
            "status": p.status,
            "pelanggan": u.nama if u else "Unknown",
            "layanan": l.nama if l else "Unknown",
            "total_harga": p.total_harga,
            "jadwal": p.jadwal,
            "created_at": p.created_at.isoformat(),
            "form_data": p.form_data,
        })
    return data

# ── Kelola Pesanan (unresolved orders with rich data) ──

@router.get("/admin/kelola-pesanan")
async def get_kelola_pesanan(request: Request, db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    unresolved = {"menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai"}
    stmt = (
        select(Pesanan)
        .where(Pesanan.status.in_(unresolved))
        .order_by(Pesanan.created_at.desc())
    )
    result = await db.execute(stmt)
    pesanan_list = result.scalars().all()
    data = []
    for p in pesanan_list:
        u = await db.get(User, p.user_id)
        l = await db.get(Layanan, p.layanan_id)
        v = await db.get(LayananVarian, p.varian_id)

        form_data_obj = {}
        if p.form_data:
            try:
                form_data_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
            except (json.JSONDecodeError, TypeError):
                form_data_obj = {}

        metode_bayar = form_data_obj.get("metode_pembayaran") or "cod"

        # Filter form fields: exclude metode_pembayaran
        form_display = {k: v for k, v in form_data_obj.items() if k != "metode_pembayaran"}

        data.append({
            "id": p.id,
            "kode": p.kode,
            "status": p.status,
            "pelanggan_nama": u.nama if u else "Unknown",
            "pelanggan_wa": u.no_hp if u else None,
            "alamat": p.alamat,
            "catatan": p.catatan,
            "jadwal": p.jadwal,
            "jam": p.jam,
            "durasi": p.durasi,
            "layanan_nama": l.nama if l else None,
            "varian_nama": v.nama if v else None,
            "total_harga": p.total_harga,
            "metode_pembayaran": metode_bayar,
            "form_data": form_display if form_display else None,
            "created_at": p.created_at.isoformat(),
        })
    return data

# ── Dashboard stats ──

@router.put("/admin/pesanan/{pesanan_id}/status")
async def update_pesanan_status(request: Request, pesanan_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    status_baru = body.get("status", "").lower().strip()
    valid_status = {"menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai", "selesai", "dibatalkan"}
    if status_baru not in valid_status:
        raise HTTPException(400, f"Status tidak valid. Pilihan: {', '.join(sorted(valid_status))}")

    result = await db.execute(select(Pesanan).where(
        (Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)
    ))
    pesanan = result.scalar_one_or_none()
    if not pesanan:
        raise HTTPException(404, "Pesanan tidak ditemukan")

    pesanan.status = status_baru
    await db.commit()
    await db.refresh(pesanan)

    return {"success": True, "kode": pesanan.kode, "status": pesanan.status}

@router.get("/admin/stats")
async def get_admin_stats(request: Request, db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    users = await db.execute(select(User))
    total_customer = sum(1 for u in users.scalars().all() if u.role == "CUSTOMER")

    pesanan_result = await db.execute(select(Pesanan))
    all_pesanan = pesanan_result.scalars().all()
    total_order = len(all_pesanan)
    today_order = sum(1 for p in all_pesanan if p.created_at.date() == datetime.now(timezone.utc).date())
    pending = sum(1 for p in all_pesanan if p.status == "menunggu")

    layanan_result = await db.execute(select(Layanan).where(Layanan.aktif == True))
    total_layanan = len(layanan_result.scalars().all())

    return {
        "total_customer": total_customer,
        "total_order": total_order,
        "today_order": today_order,
        "pending_order": pending,
        "total_layanan": total_layanan,
    }
