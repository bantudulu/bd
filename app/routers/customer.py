import json

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse

from app.templates import render
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["customer"])

def require_auth(request: Request):
    if not request.state.user:
        return None
    return request.state.user

@router.get("/beranda")
async def beranda(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    from app.models import Kategori, Layanan, LayananVarian
    from sqlalchemy import select

    # SSR: fetch kategori
    kat_res = await db.execute(select(Kategori).order_by(Kategori.urutan))
    kategori_list = kat_res.scalars().all()
    categories = [
        {"id": k.id, "nama": k.nama, "icon": k.icon, "slug": k.slug}
        for k in kategori_list
    ]

    # SSR: fetch layanan populer
    lay_res = await db.execute(select(Layanan).where(Layanan.aktif == True))
    layanan_list = lay_res.scalars().all()
    services = []
    for l in layanan_list[:4]:
        v_res = await db.execute(
            select(LayananVarian.harga).where(LayananVarian.layanan_id == l.id).order_by(LayananVarian.harga).limit(1)
        )
        min_price = v_res.scalar() or 0
        services.append({
            "id": l.id,
            "nama": l.nama,
            "deskripsi": l.deskripsi,
            "harga_min": min_price,
        })

    return render("customer/beranda.html", user=user, categories=categories, services=services)

@router.get("/cari")
async def cari_page(request: Request):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")
    return render("customer/cari.html", user=user)

@router.get("/pesanan")
async def pesanan_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    # SSR: fetch user's orders
    from app.models import Pesanan, Layanan, LayananVarian
    from sqlalchemy import select

    stmt = select(Pesanan).where(Pesanan.user_id == user.get("id")).order_by(Pesanan.created_at.desc())
    result = await db.execute(stmt)
    pesanan_list = result.scalars().all()

    orders = []
    for p in pesanan_list:
        l = await db.get(Layanan, p.layanan_id)
        orders.append({
            "kode": p.kode,
            "id": p.id,
            "status": p.status,
            "layanan_nama": l.nama if l else "Pesanan",
            "varian_nama": "",
            "total_harga": p.total_harga,
            "tanggal": p.jadwal or p.created_at.isoformat(),
            "created_at": p.created_at.isoformat(),
            "kategori_nama": "",
        })

    import json as json_mod
    orders_json = json_mod.dumps(orders, default=str)

    return render("customer/pesanan.html", user=user, orders=orders, orders_json=orders_json)

@router.get("/profil")
async def profil_page(request: Request):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")
    return render("customer/profil.html", user=user)

# Map slug → background image filename
KATEGORI_IMAGES = {
    "bersih": "bg-bersih.png",
    "elektronik": "bg-elektronik.png",
    "les": "bg-les.png",
    "pijat": "bg-pijat.png",
    "salon": "bg-salon.png",
    "belanja": "bg-belanja.png",
}

@router.get("/kategori-lama/{slug}")
async def kategori_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    from app.models import Kategori, Layanan, LayananVarian
    from sqlalchemy import select

    # SSR: fetch kategori by slug
    kat_res = await db.execute(select(Kategori).where(Kategori.slug == slug))
    kategori = kat_res.scalar_one_or_none()

    kat_data = None
    layanan_data = []
    if kategori:
        kat_data = {"id": kategori.id, "nama": kategori.nama, "icon": kategori.icon, "slug": kategori.slug}

        # SSR: fetch layanan by kategori_id
        lay_res = await db.execute(
            select(Layanan).where(Layanan.kategori_id == kategori.id, Layanan.aktif == True)
        )
        layanan_list = lay_res.scalars().all()
        for l in layanan_list:
            v_res = await db.execute(
                select(LayananVarian.harga).where(LayananVarian.layanan_id == l.id).order_by(LayananVarian.harga).limit(1)
            )
            min_price = v_res.scalar() or 0
            layanan_data.append({
                "id": l.id,
                "nama": l.nama,
                "deskripsi": l.deskripsi,
                "harga_min": min_price,
            })

    bg_image = KATEGORI_IMAGES.get(slug, "bg-beranda.png")

    return render("customer/kategori.html", user=user, kategori=kat_data, layanan=layanan_data, bg_image=bg_image)

@router.get("/pesan/{layanan_id}")
async def pesan_page(request: Request, layanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    # SSR: fetch layanan data untuk variant + form fields
    from app.models import Layanan, LayananVarian, FormField, Kategori
    from sqlalchemy import select

    result = await db.execute(select(Layanan).where(Layanan.id == layanan_id))
    layanan = result.scalar_one_or_none()

    svc_data = None
    if layanan:
        varian_res = await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == layanan_id))
        varian_list = varian_res.scalars().all()

        fields_res = await db.execute(
            select(FormField).where(FormField.layanan_id == layanan_id).order_by(FormField.urutan)
        )
        fields_list = fields_res.scalars().all()
        import logging
        logging.warning(f"PESAN DEBUG: layanan={layanan.nama}, varian={len(varian_list)}, fields={len(fields_list)}")

        kat_res = await db.execute(select(Kategori).where(Kategori.id == layanan.kategori_id))
        kategori = kat_res.scalar_one()

        svc_data = {
            "id": layanan.id,
            "nama": layanan.nama,
            "deskripsi": layanan.deskripsi,
            "catatan": layanan.catatan,
            "jenis_layanan": layanan.jenis_layanan,
            "tipe_hitung": layanan.tipe_hitung,
            "kategori_nama": kategori.nama,
            "kategori_icon": kategori.icon,
            "kategori_warna": kategori.warna,
            "kategori_slug": kategori.slug,
            "varian": [{"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi} for v in varian_list],
            "form_fields": [{"id": f.id, "label": f.label, "field_type": f.field_type, "required": f.required, "options": json.loads(f.options) if f.options else [], "harga_tambahan": f.harga_tambahan} for f in fields_list],
        }

    return render("customer/pesan.html", user=user, layanan_id=layanan_id, svc_data=svc_data)

@router.get("/layanan/{layanan_id}")
async def layanan_detail_page(request: Request, layanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    # Fetch layanan data server-side untuk SSR (loading langsung)
    from app.models import Layanan, LayananVarian, FormField, Kategori
    from sqlalchemy import select

    result = await db.execute(select(Layanan).where(Layanan.id == layanan_id))
    layanan = result.scalar_one_or_none()

    svc_data = None
    if layanan:
        varian_res = await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == layanan_id))
        varian_list = varian_res.scalars().all()

        fields_res = await db.execute(select(FormField).where(FormField.layanan_id == layanan_id).order_by(FormField.urutan))
        fields_list = fields_res.scalars().all()

        kat_res = await db.execute(select(Kategori).where(Kategori.id == layanan.kategori_id))
        kategori = kat_res.scalar_one()

        # Sub-opsi dari form field select bertipe harga (format opsi: "Nama|tambah_harga")
        # Contoh: ["Pekerjaan Ringan|0", "Pekerjaan Berat|30000"]
        sub_options = []
        for f in fields_list:
            if f.field_type == "select" and f.options:
                try:
                    opts = json.loads(f.options)
                except Exception:
                    opts = []
                if opts and all("|" in str(o) for o in opts):
                    sub_options = [
                        {"nama": str(o).split("|")[0].strip(), "tambah": int(str(o).split("|")[1].strip() or 0)}
                        for o in opts
                    ]
                    break

        varian_data = []
        for v in varian_list:
            vd = {"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi}
            if sub_options:
                vd["sub_opsi"] = [{"nama": s["nama"], "harga": v.harga + s["tambah"]} for s in sub_options]
            varian_data.append(vd)

        svc_data = {
            "id": layanan.id,
            "nama": layanan.nama,
            "deskripsi": layanan.deskripsi,
            "catatan": layanan.catatan,
            "jenis_layanan": layanan.jenis_layanan,
            "tipe_hitung": layanan.tipe_hitung,
            "kategori_nama": kategori.nama,
            "kategori_icon": kategori.icon,
            "kategori_warna": kategori.warna,
            "kategori_slug": kategori.slug,
            "varian": varian_data,
            "form_fields": [{"id": f.id, "label": f.label, "field_type": f.field_type, "required": f.required, "options": json.loads(f.options) if f.options else [], "harga_tambahan": f.harga_tambahan} for f in fields_list],
        }

        # Tambah kategori_image untuk ditampilkan di halaman layanan
        svc_data["kategori_image"] = KATEGORI_IMAGES.get(kategori.slug, "bg-beranda.png")

    return render("customer/layanan_detail.html", user=user, layanan_id=layanan_id, svc_data=svc_data)

@router.get("/pesanan/{pesanan_id}")
async def pesanan_detail_page(request: Request, pesanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return RedirectResponse(url="/masuk")

    # SSR: fetch order detail
    from app.models import Pesanan, Layanan, LayananVarian, User
    from sqlalchemy import select
    import json as json_mod

    result = await db.execute(
        select(Pesanan).where(
            (Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)
        )
    )
    p = result.scalar_one_or_none()
    if p and user.get("role") != "ADMIN" and p.user_id != user.get("id"):
        p = None

    order = None
    if p:
        l = await db.get(Layanan, p.layanan_id)
        v = await db.get(LayananVarian, p.varian_id)
        u = await db.get(User, p.user_id)

        form_data_obj = {}
        if p.form_data:
            try:
                form_data_obj = json_mod.loads(p.form_data) if isinstance(p.form_data, str) else p.form_data
            except (json_mod.JSONDecodeError, TypeError):
                form_data_obj = {}
        metode_pembayaran = form_data_obj.get("metode_pembayaran") or "cod"

        waktu_label = ""
        if p.jadwal:
            waktu_label = p.jadwal
            if p.jam:
                waktu_label += " • " + p.jam

        order = {
            "kode": p.kode,
            "status": p.status,
            "layanan_nama": l.nama if l else "-",
            "varian_nama": v.nama if v else "",
            "alamat": p.alamat or "-",
            "tanggal": p.jadwal or "-",
            "jam": p.jam or "-",
            "total_harga": p.total_harga or 0,
            "catatan": p.catatan or "",
            "metode_pembayaran": metode_pembayaran,
            "wa_kontak": u.no_hp if u else None,
            "pelanggan_nama": u.nama if u else None,
        }

    return render("customer/pesanan_detail.html", user=user, pesanan_id=pesanan_id, order=order)

@router.get("/akun")
async def akun_page(request: Request):
    return await profil_page(request)

@router.get("/tentang-hallmark")
async def hallmark_demo(request: Request):
    """Contoh halaman dengan prinsip Hallmark — anti-AI-slop design"""
    user = require_auth(request)
    return render("customer/hallmark_demo.html", request=request, user=user)
