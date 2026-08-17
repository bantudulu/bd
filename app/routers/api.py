import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domain import ACTIVE_ORDER_STATUSES, VALID_ORDER_STATUSES
from app.models import FormField, Kategori, Layanan, LayananVarian, Pesanan, User
from app.query_services import order_related_maps, service_min_prices

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/kategori")
async def get_kategori(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Kategori).order_by(Kategori.urutan))
    return [{"id": k.id, "nama": k.nama, "icon": k.icon, "slug": k.slug, "warna": k.warna} for k in result.scalars().all()]


@router.get("/layanan")
async def get_layanan(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Layanan).where(Layanan.aktif == True))  # noqa: E712
    rows = list(result.scalars().all())
    prices = await service_min_prices(db, [row.id for row in rows])
    return [{"id": row.id, "kategori_id": row.kategori_id, "nama": row.nama, "deskripsi": row.deskripsi, "jenis_layanan": row.jenis_layanan, "tipe_hitung": row.tipe_hitung, "gambar_url": row.gambar_url, "harga_min": prices.get(row.id, 0)} for row in rows]


@router.get("/layanan/{layanan_id}")
async def get_layanan_detail(layanan_id: str, db: AsyncSession = Depends(get_db)):
    layanan = await db.get(Layanan, layanan_id)
    if not layanan:
        raise HTTPException(404, "Layanan tidak ditemukan")
    varian_result = await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == layanan_id))
    fields_result = await db.execute(select(FormField).where(FormField.layanan_id == layanan_id).order_by(FormField.urutan))
    kat = await db.get(Kategori, layanan.kategori_id)
    return {"layanan": {"id": layanan.id, "nama": layanan.nama, "deskripsi": layanan.deskripsi, "catatan": layanan.catatan, "jenis_layanan": layanan.jenis_layanan, "tipe_hitung": layanan.tipe_hitung, "kategori": {"nama": kat.nama, "icon": kat.icon, "warna": kat.warna} if kat else None}, "varian": [{"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi} for v in varian_result.scalars().all()], "form_fields": [{"id": f.id, "label": f.label, "field_type": f.field_type, "options": json.loads(f.options) if f.options else [], "required": f.required, "harga_tambahan": f.harga_tambahan} for f in fields_result.scalars().all()]}


def _order_rows_payload(rows, related):
    data = []
    for p in rows:
        layanan = related["services"].get(p.layanan_id)
        varian = related["variants"].get(p.varian_id)
        user = related["users"].get(p.user_id)
        data.append({"id": p.id, "kode": p.kode, "status": p.status, "alamat": p.alamat, "tanggal": p.jadwal, "jadwal": p.jadwal, "jam": p.jam, "durasi": p.durasi, "total_harga": p.total_harga, "harga": p.total_harga, "catatan": p.catatan, "form_data": p.form_data, "no_wa": user.no_hp if user else None, "wa_kontak": user.no_hp if user else None, "layanan_nama": layanan.nama if layanan else None, "varian_nama": varian.nama if varian else None, "created_at": p.created_at.isoformat()})
    return data


@router.get("/pesanan")
async def get_pesanan(user_id: str = Query(None), status: str = Query(None), limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    stmt = select(Pesanan)
    if user_id:
        stmt = stmt.where(Pesanan.user_id == user_id)
    if status:
        stmt = stmt.where(Pesanan.status == status)
    result = await db.execute(stmt.order_by(Pesanan.created_at.desc()).offset(offset).limit(limit))
    rows = list(result.scalars().all())
    return _order_rows_payload(rows, await order_related_maps(db, rows))


@router.get("/pesanan/aktif")
async def get_pesanan_aktif(request: Request, db: AsyncSession = Depends(get_db)):
    from app.auth import get_user_from_request
    user = get_user_from_request(request)
    if not user or not user.get("id"):
        return []
    result = await db.execute(select(Pesanan).where(Pesanan.user_id == user["id"], Pesanan.status.in_(ACTIVE_ORDER_STATUSES)).order_by(Pesanan.created_at.desc()).limit(5))
    rows = list(result.scalars().all())
    related = await order_related_maps(db, rows)
    return {"data": [{"id": p.id, "kode": p.kode, "status": p.status, "alamat": p.alamat, "total_harga": p.total_harga, "layanan_nama": related["services"].get(p.layanan_id).nama if related["services"].get(p.layanan_id) else "Pesanan", "created_at": p.created_at.isoformat()} for p in rows]}


@router.get("/pesanan/{pesanan_id}")
async def get_pesanan_detail(pesanan_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pesanan).where((Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Pesanan tidak ditemukan")
    related = await order_related_maps(db, [p])
    layanan = related["services"].get(p.layanan_id)
    varian = related["variants"].get(p.varian_id)
    user = related["users"].get(p.user_id)
    form_data_obj = {}
    if p.form_data:
        try:
            form_data_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
        except (json.JSONDecodeError, TypeError):
            form_data_obj = {}
    return {"id": p.id, "kode": p.kode, "status": p.status, "alamat": p.alamat, "tanggal": p.jadwal, "jadwal": p.jadwal, "jam": p.jam, "durasi": p.durasi, "total_harga": p.total_harga, "harga": p.total_harga, "catatan": p.catatan, "form_data": p.form_data, "metode_pembayaran": form_data_obj.get("metode_pembayaran") or "cod", "created_at": p.created_at.isoformat(), "layanan_nama": layanan.nama if layanan else None, "varian_nama": varian.nama if varian else None, "pelanggan_nama": user.nama if user else None, "no_wa": user.no_hp if user else None, "wa_kontak": user.no_hp if user else None}


def require_admin_api(request: Request):
    user = request.state.user
    if not user or user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya admin.")
    return user


@router.get("/admin/pesanan")
async def get_all_pesanan(request: Request, status: str = Query(None), limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    stmt = select(Pesanan)
    if status:
        stmt = stmt.where(Pesanan.status == status)
    result = await db.execute(stmt.order_by(Pesanan.created_at.desc()).offset(offset).limit(limit))
    rows = list(result.scalars().all())
    related = await order_related_maps(db, rows)
    return [{"id": p.id, "kode": p.kode, "status": p.status, "pelanggan": related["users"].get(p.user_id).nama if related["users"].get(p.user_id) else "Unknown", "layanan": related["services"].get(p.layanan_id).nama if related["services"].get(p.layanan_id) else "Unknown", "total_harga": p.total_harga, "jadwal": p.jadwal, "created_at": p.created_at.isoformat(), "form_data": p.form_data} for p in rows]


@router.get("/admin/kelola-pesanan")
async def get_kelola_pesanan(request: Request, limit: int = Query(100, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    result = await db.execute(select(Pesanan).where(Pesanan.status.in_(ACTIVE_ORDER_STATUSES)).order_by(Pesanan.created_at.desc()).limit(limit))
    rows = list(result.scalars().all())
    related = await order_related_maps(db, rows)
    data = []
    for p in rows:
        user = related["users"].get(p.user_id)
        layanan = related["services"].get(p.layanan_id)
        varian = related["variants"].get(p.varian_id)
        form_obj = {}
        if p.form_data:
            try:
                form_obj = json.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
            except (json.JSONDecodeError, TypeError):
                form_obj = {}
        data.append({"id": p.id, "kode": p.kode, "status": p.status, "pelanggan_nama": user.nama if user else "Unknown", "pelanggan_wa": user.no_hp if user else None, "alamat": p.alamat, "catatan": p.catatan, "jadwal": p.jadwal, "jam": p.jam, "durasi": p.durasi, "layanan_nama": layanan.nama if layanan else None, "varian_nama": varian.nama if varian else None, "total_harga": p.total_harga, "metode_pembayaran": form_obj.get("metode_pembayaran") or "cod", "form_data": {k: v for k, v in form_obj.items() if k != "metode_pembayaran"} or None, "created_at": p.created_at.isoformat()})
    return data


@router.put("/admin/pesanan/{pesanan_id}/status")
async def update_pesanan_status(request: Request, pesanan_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    require_admin_api(request)
    status_baru = body.get("status", "").lower().strip()
    if status_baru not in VALID_ORDER_STATUSES:
        raise HTTPException(400, f"Status tidak valid. Pilihan: {', '.join(sorted(VALID_ORDER_STATUSES))}")
    result = await db.execute(select(Pesanan).where((Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)))
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
    today = datetime.now(timezone.utc).date()
    total_customer = int((await db.execute(select(func.count(User.id)).where(User.role == "CUSTOMER"))).scalar() or 0)
    total_order = int((await db.execute(select(func.count(Pesanan.id)))).scalar() or 0)
    pending = int((await db.execute(select(func.count(Pesanan.id)).where(Pesanan.status == "menunggu"))).scalar() or 0)
    total_layanan = int((await db.execute(select(func.count(Layanan.id)).where(Layanan.aktif == True))).scalar() or 0)  # noqa: E712
    all_today = await db.execute(select(Pesanan.created_at).where(Pesanan.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)))
    today_order = len(all_today.scalars().all())
    return {"total_customer": total_customer, "total_order": total_order, "today_order": today_order, "pending_order": pending, "total_layanan": total_layanan}
