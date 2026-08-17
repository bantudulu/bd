import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models import Pesanan, Layanan, LayananVarian, User
from app.auth import get_user_from_request

router = APIRouter(prefix="/api", tags=["api"])

@router.post("/pesanan")
async def create_pesanan(
    request: Request,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    # Validasi login
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Silakan login terlebih dahulu")

    user_id = user.get("id")
    if not user_id:
        raise HTTPException(401, "Session tidak valid")

    # Validasi field wajib
    layanan_id = data.get("layanan_id")
    varian_id = data.get("varian_id")
    if not layanan_id:
        raise HTTPException(400, "Field layanan_id wajib diisi")
    if not varian_id:
        raise HTTPException(400, "Field varian_id wajib diisi")

    # Ambil data varian untuk harga
    varian = await db.get(LayananVarian, varian_id)
    if not varian:
        raise HTTPException(404, "Varian tidak ditemukan")

    # Ambil form_data dari body
    form_data_raw = data.get("form_data", {})
    metode_pembayaran = data.get("metode_pembayaran", "cod")

    # Ekstrak alamat & jadwal dari form_data jika ada
    alamat = data.get("alamat") or form_data_raw.get("field_alamat") or ""
    jadwal = data.get("jadwal") or form_data_raw.get("field_jadwal") or ""
    jam = data.get("jam") or form_data_raw.get("field_jam") or ""
    catatan = data.get("catatan") or form_data_raw.get("field_catatan") or ""

    import logging
    logger = logging.getLogger('bantudulu')

    # Ambil durasi dari body (default 1)
    raw_durasi = data.get("durasi", None)
    durasi = int(raw_durasi or 1)
    if durasi < 1:
        durasi = 1

    # Ambil addon_total dari body (default 0)
    addon_total = int(data.get("addon_total") or 0)
    if addon_total < 0:
        addon_total = 0

    # Hitung total berdasarkan durasi + addon
    total = varian.harga * durasi + addon_total

    # Biaya tambahan Lantai 2+ untuk Cuci Tandon Air
    for k, v in form_data_raw.items():
        if isinstance(v, str) and 'Lantai 2+' in v:
            total += 50000
            break

    # Buat kode unik
    kode = f"BD-{uuid.uuid4().hex[:6].upper()}"

    # Siapkan form_data — simpan metode_pembayaran + field lainnya
    simpan_form = {"metode_pembayaran": metode_pembayaran}
    for k, v in form_data_raw.items():
        if k not in ("field_alamat", "field_jadwal", "field_jam", "field_catatan"):
            simpan_form[k] = v

    order = Pesanan(
        user_id=user_id,
        layanan_id=layanan_id,
        varian_id=varian_id,
        kode=kode,
        status="menunggu",
        alamat=alamat,
        jadwal=jadwal,
        jam=jam,
        durasi=durasi,
        total_harga=total,
        catatan=catatan,
        form_data=json.dumps(simpan_form, ensure_ascii=False) if simpan_form else "{}",
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)

    return {
        "success": True,
        "data": {
            "id": order.id,
            "kode": order.kode,
            "status": order.status,
        }
    }
