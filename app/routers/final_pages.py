from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.templates import render

router = APIRouter(tags=["final-pages"])


def user_required(request: Request):
    return request.state.user


def admin_required(request: Request):
    user = request.state.user
    return user if user and user.get("role") == "ADMIN" else None


@router.get("/layanan")
async def layanan(request: Request):
    if not user_required(request):
        return RedirectResponse("/masuk")
    return render("customer/cari.html", user=request.state.user)


@router.get("/pesan-final")
async def pesan_final(request: Request):
    if not user_required(request):
        return RedirectResponse("/masuk")
    return render("customer/jadwal_pembayaran.html", user=request.state.user)


@router.get("/loading")
async def loading():
    return render("customer/loading.html")


@router.get("/kategori/{slug}")
async def kategori_final(request: Request, slug: str):
    if not user_required(request):
        return RedirectResponse("/masuk")

    mapping = {
        "bersih": "customer/cleaning.html",
        "antar": "customer/jasa_antar.html",
        "pijat": "customer/pijat_relaksasi.html",
        "mua": "customer/jasa_mua.html",
        "helper": "customer/helper.html",
        "dekor": "customer/dekor.html",
    }
    if slug in mapping:
        return render(mapping[slug], user=request.state.user)

    if slug == "tukang":
        return render(
            "customer/category_special.html",
            user=request.state.user,
            category_key="tukang",
            title="Tukang",
            subtitle="Perbaikan rumah yang Anda butuhkan",
            description="Pilih jenis perbaikan, tentukan durasi, lalu atur jadwal dan pembayaran.",
            section_title="Pilih jenis perbaikan",
            section_copy="Harga jasa dihitung per jam. Material atau onderdil tidak termasuk.",
            options=[
                {"service":"Tukang","variant":"Kelistrikan","label":"Kelistrikan","description":"Perbaikan dan instalasi listrik, lampu, saklar, stop kontak, dan panel.","price":70000},
                {"service":"Tukang","variant":"Perpipaan","label":"Perpipaan","description":"Perbaikan pipa, kran bocor, saluran mampet, toilet, dan instalasi air.","price":70000},
            ],
        )

    if slug == "web-desain":
        return render(
            "customer/category_special.html",
            user=request.state.user,
            category_key="web-desain",
            title="Web Desain",
            subtitle="Website untuk kebutuhan bisnis Anda",
            description="Pilih jenis website, lalu lanjutkan ke jadwal dan pembayaran BantuDulu.",
            section_title="Pilih layanan website",
            section_copy="Harga awal mengikuti paket. Kebutuhan tambahan dapat dibahas setelah pesanan dibuat.",
            options=[
                {"service":"Website Biasa","variant":"Standar","label":"Website Biasa","description":"Landing page atau profil usaha sederhana, maksimal 5 halaman.","price":500000},
                {"service":"Website Company","variant":"Mulai","label":"Website Company","description":"Website perusahaan profesional dengan beberapa halaman dan fitur bisnis.","price":1000000},
            ],
        )

    return RedirectResponse("/layanan")


@router.get("/admin/mitra")
async def admin_mitra(request: Request):
    if not admin_required(request):
        return RedirectResponse("/masuk")
    return render("admin/mitra.html", user=request.state.user)


@router.get("/admin/transaksi")
async def admin_transaksi(request: Request):
    if not admin_required(request):
        return RedirectResponse("/masuk")
    return render("admin/transaksi.html", user=request.state.user)


@router.get("/admin/pengaturan")
async def admin_pengaturan(request: Request):
    if not admin_required(request):
        return RedirectResponse("/masuk")
    return render("admin/pengaturan.html", user=request.state.user)
