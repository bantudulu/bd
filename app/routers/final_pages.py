from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.templates import render

router = APIRouter(tags=["final-pages"])


def user_required(request: Request):
    return request.state.user


def admin_required(request: Request):
    user=request.state.user
    return user if user and user.get("role")=="ADMIN" else None


@router.get("/layanan")
async def layanan(request: Request):
    if not user_required(request): return RedirectResponse("/masuk")
    return render("customer/cari.html", user=request.state.user)


@router.get("/pesan-final")
async def pesan_final(request: Request):
    if not user_required(request): return RedirectResponse("/masuk")
    return render("customer/jadwal_pembayaran.html", user=request.state.user)


@router.get("/loading")
async def loading():
    return render("customer/loading.html")


@router.get("/kategori/{slug}")
async def kategori_final(request: Request, slug: str):
    if not user_required(request): return RedirectResponse("/masuk")
    mapping={"bersih":"customer/cleaning.html","antar":"customer/jasa_antar.html","pijat":"customer/pijat_relaksasi.html","mua":"customer/jasa_mua.html","helper":"customer/helper.html","dekor":"customer/dekor.html"}
    if slug in mapping: return render(mapping[slug], user=request.state.user)
    # Belum ada halaman FINAL khusus Tukang/Web Desain pada paket sumber; pertahankan jalur lama untuk fungsi booking.
    return RedirectResponse(f"/kategori-lama/{slug}")


@router.get("/admin/mitra")
async def admin_mitra(request: Request):
    if not admin_required(request): return RedirectResponse("/masuk")
    return render("admin/mitra.html", user=request.state.user)

@router.get("/admin/transaksi")
async def admin_transaksi(request: Request):
    if not admin_required(request): return RedirectResponse("/masuk")
    return render("admin/transaksi.html", user=request.state.user)

@router.get("/admin/pengaturan")
async def admin_pengaturan(request: Request):
    if not admin_required(request): return RedirectResponse("/masuk")
    return render("admin/pengaturan.html", user=request.state.user)
