import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.templates import render

router = APIRouter(tags=["customer"])

KATEGORI_IMAGES = {
    "bersih": "bg-bersih.png",
    "elektronik": "bg-elektronik.png",
    "les": "bg-les.png",
    "pijat": "bg-pijat.png",
    "salon": "bg-salon.png",
    "belanja": "bg-belanja.png",
}


def require_auth(request: Request):
    return request.state.user or None


def _redirect_login():
    return RedirectResponse(url="/masuk")


def _safe_options(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def _service_payload(db: AsyncSession, layanan_id: str):
    from app.models import FormField, Kategori, Layanan, LayananVarian

    layanan = await db.get(Layanan, layanan_id)
    if not layanan or not layanan.aktif:
        return None

    variants_result = await db.execute(
        select(LayananVarian).where(LayananVarian.layanan_id == layanan.id)
    )
    variants = variants_result.scalars().all()
    fields_result = await db.execute(
        select(FormField)
        .where(FormField.layanan_id == layanan.id)
        .order_by(FormField.urutan)
    )
    fields = fields_result.scalars().all()
    kategori = await db.get(Kategori, layanan.kategori_id)

    return {
        "id": layanan.id,
        "nama": layanan.nama,
        "deskripsi": layanan.deskripsi,
        "catatan": layanan.catatan,
        "jenis_layanan": layanan.jenis_layanan,
        "tipe_hitung": layanan.tipe_hitung,
        "kategori_nama": kategori.nama if kategori else "",
        "kategori_icon": kategori.icon if kategori else "📦",
        "kategori_warna": kategori.warna if kategori else "#042544",
        "kategori_slug": kategori.slug if kategori else "",
        "kategori_image": KATEGORI_IMAGES.get(kategori.slug if kategori else "", "bg-beranda.png"),
        "varian": [
            {"id": v.id, "nama": v.nama, "harga": v.harga, "deskripsi": v.deskripsi}
            for v in variants
        ],
        "form_fields": [
            {
                "id": f.id,
                "label": f.label,
                "field_type": f.field_type,
                "required": f.required,
                "options": _safe_options(f.options),
                "harga_tambahan": f.harga_tambahan,
            }
            for f in fields
        ],
    }


@router.get("/beranda")
async def beranda(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()

    from app.models import Kategori, Layanan, LayananVarian, Notifikasi

    kat_result = await db.execute(select(Kategori).order_by(Kategori.urutan))
    categories = [
        {"id": k.id, "nama": k.nama, "icon": k.icon, "slug": k.slug}
        for k in kat_result.scalars().all()
    ]

    layanan_result = await db.execute(
        select(Layanan).where(Layanan.aktif == True).limit(4)  # noqa: E712
    )
    services = []
    for layanan in layanan_result.scalars().all():
        price_result = await db.execute(
            select(LayananVarian.harga)
            .where(LayananVarian.layanan_id == layanan.id)
            .order_by(LayananVarian.harga)
            .limit(1)
        )
        services.append({
            "id": layanan.id,
            "nama": layanan.nama,
            "deskripsi": layanan.deskripsi,
            "harga_min": price_result.scalar() or 0,
        })

    unread_result = await db.execute(
        select(Notifikasi.id).where(
            Notifikasi.user_id == user.get("id"),
            Notifikasi.dibaca == False,  # noqa: E712
        )
    )
    unread_notifications = len(unread_result.scalars().all())

    return render(
        "customer/beranda.html",
        user=user,
        categories=categories,
        services=services,
        unread_notifications=unread_notifications,
    )


@router.get("/cari")
async def cari_page(request: Request):
    user = require_auth(request)
    if not user:
        return _redirect_login()
    return render("customer/cari.html", user=user)


@router.get("/pesanan")
async def pesanan_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()

    from app.models import Layanan, LayananVarian, Pesanan

    result = await db.execute(
        select(Pesanan)
        .where(Pesanan.user_id == user.get("id"))
        .order_by(Pesanan.created_at.desc())
    )
    rows = result.scalars().all()
    orders = []
    for order in rows:
        layanan = await db.get(Layanan, order.layanan_id)
        varian = await db.get(LayananVarian, order.varian_id)
        orders.append({
            "kode": order.kode,
            "id": order.id,
            "status": order.status,
            "layanan_nama": layanan.nama if layanan else "Pesanan",
            "varian_nama": varian.nama if varian else "",
            "total_harga": order.total_harga,
            "tanggal": order.jadwal or order.created_at.isoformat(),
            "created_at": order.created_at.isoformat(),
            "kategori_nama": layanan.jenis_layanan if layanan else "",
        })

    return render(
        "customer/pesanan.html",
        user=user,
        orders=orders,
        orders_json=json.dumps(orders, default=str),
    )


@router.get("/profil")
async def profil_page(request: Request):
    user = require_auth(request)
    if not user:
        return _redirect_login()
    return render("customer/profil.html", user=user)


@router.get("/kategori/{slug}")
async def kategori_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()

    from app.models import Kategori, Layanan, LayananVarian

    kat_result = await db.execute(select(Kategori).where(Kategori.slug == slug))
    kategori = kat_result.scalar_one_or_none()
    kategori_data = None
    layanan_data = []

    if kategori:
        kategori_data = {
            "id": kategori.id,
            "nama": kategori.nama,
            "icon": kategori.icon,
            "slug": kategori.slug,
        }
        layanan_result = await db.execute(
            select(Layanan).where(
                Layanan.kategori_id == kategori.id,
                Layanan.aktif == True,  # noqa: E712
            )
        )
        for layanan in layanan_result.scalars().all():
            price_result = await db.execute(
                select(LayananVarian.harga)
                .where(LayananVarian.layanan_id == layanan.id)
                .order_by(LayananVarian.harga)
                .limit(1)
            )
            layanan_data.append({
                "id": layanan.id,
                "nama": layanan.nama,
                "deskripsi": layanan.deskripsi,
                "harga_min": price_result.scalar() or 0,
            })

    return render(
        "customer/kategori.html",
        user=user,
        kategori=kategori_data,
        layanan=layanan_data,
        bg_image=KATEGORI_IMAGES.get(slug, "bg-beranda.png"),
    )


@router.get("/pesan/{layanan_id}")
async def pesan_page(request: Request, layanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()
    svc_data = await _service_payload(db, layanan_id)
    return render("customer/pesan.html", user=user, layanan_id=layanan_id, svc_data=svc_data)


@router.get("/layanan/{layanan_id}")
async def layanan_detail_page(request: Request, layanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()

    svc_data = await _service_payload(db, layanan_id)
    if svc_data:
        priced_options = []
        for field in svc_data["form_fields"]:
            options = field.get("options") or []
            if field.get("field_type") == "select" and options and all("|" in str(o) for o in options):
                for option in options:
                    name, raw_price = str(option).split("|", 1)
                    try:
                        priced_options.append({"nama": name.strip(), "tambah": int(raw_price.strip() or 0)})
                    except ValueError:
                        pass
                break
        if priced_options:
            for variant in svc_data["varian"]:
                variant["sub_opsi"] = [
                    {"nama": item["nama"], "harga": variant["harga"] + item["tambah"]}
                    for item in priced_options
                ]

    return render("customer/layanan_detail.html", user=user, layanan_id=layanan_id, svc_data=svc_data)


@router.get("/pesanan/{pesanan_id}")
async def pesanan_detail_page(request: Request, pesanan_id: str, db: AsyncSession = Depends(get_db)):
    user = require_auth(request)
    if not user:
        return _redirect_login()

    from app.models import Assignment, Layanan, LayananVarian, Pesanan, Petugas

    result = await db.execute(
        select(Pesanan).where(
            (Pesanan.id == pesanan_id) | (Pesanan.kode == pesanan_id)
        )
    )
    row = result.scalar_one_or_none()
    if row and row.user_id != user.get("id") and user.get("role") != "ADMIN":
        row = None

    order = None
    if row:
        layanan = await db.get(Layanan, row.layanan_id)
        varian = await db.get(LayananVarian, row.varian_id)
        form_data = {}
        if row.form_data:
            try:
                form_data = json.loads(row.form_data) if isinstance(row.form_data, str) else row.form_data
            except (json.JSONDecodeError, TypeError):
                form_data = {}

        assignment_result = await db.execute(
            select(Assignment)
            .where(
                Assignment.pesanan_id == row.id,
                Assignment.status == "aktif",
            )
            .order_by(Assignment.assigned_at.desc())
            .limit(1)
        )
        assignment = assignment_result.scalar_one_or_none()
        petugas = await db.get(Petugas, assignment.petugas_id) if assignment else None

        status = (row.status or "menunggu").lower()
        steps = [
            ("menunggu", "Menunggu Petugas", "Pesanan sudah diterima dan tim BantuDulu sedang menyiapkan petugas."),
            ("ditugaskan", "Petugas Ditugaskan", "Petugas sudah ditentukan untuk pesanan Anda."),
            ("menuju_lokasi", "Menuju Lokasi", "Petugas sedang menuju alamat layanan."),
            ("dimulai", "Sedang Dikerjakan", "Layanan sedang dikerjakan oleh petugas."),
            ("selesai", "Selesai", "Pesanan selesai dikerjakan."),
        ]
        rank = {key: index for index, (key, _, _) in enumerate(steps)}
        current_rank = rank.get(status, 0)
        timeline = [
            {
                "key": key,
                "label": label,
                "description": description,
                "state": "done" if current_rank > index else "current" if current_rank == index else "upcoming",
            }
            for index, (key, label, description) in enumerate(steps)
        ]

        order = {
            "id": row.id,
            "kode": row.kode,
            "status": status,
            "layanan_nama": layanan.nama if layanan else "-",
            "varian_nama": varian.nama if varian else "",
            "alamat": row.alamat or "-",
            "tanggal": row.jadwal or "-",
            "jam": row.jam or "-",
            "durasi": row.durasi,
            "total_harga": row.total_harga or 0,
            "catatan": row.catatan or "",
            "metode_pembayaran": form_data.get("metode_pembayaran") or "cod",
            "timeline": timeline,
            "petugas": {
                "nama": petugas.nama,
                "foto": petugas.foto,
                "wilayah": petugas.wilayah,
            } if petugas else None,
            "dibatalkan": status == "dibatalkan",
        }

    return render("customer/pesanan_detail.html", user=user, pesanan_id=pesanan_id, order=order)


@router.get("/akun")
async def akun_page(request: Request):
    return await profil_page(request)


@router.get("/tentang-hallmark")
async def hallmark_demo(request: Request):
    user = require_auth(request)
    return render("customer/hallmark_demo.html", request=request, user=user)
