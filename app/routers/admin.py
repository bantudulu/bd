from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.templates import render

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin-only page ──
@router.get("/pesanan/{pesanan_id}")
async def admin_pesanan_detail(request: Request, pesanan_id: str):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/pesanan_detail.html", user=admin, pesanan_id=pesanan_id)

@router.get("/kelola")
async def admin_kelola(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/kelola.html", user=admin)

def require_admin(request: Request):
    user = request.state.user
    if not user or user.get("role") != "ADMIN":
        return None
    return user

@router.get("/dashboard")
async def admin_dashboard(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/dashboard.html", user=admin)

@router.get("/pesanan")
async def admin_pesanan(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/pesanan.html", user=admin)

@router.get("/layanan")
async def admin_layanan(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/layanan.html", user=admin)

@router.get("/laporan")
async def admin_laporan(request: Request):
    admin = require_admin(request)
    if not admin:
        return RedirectResponse(url="/masuk")
    return render("admin/laporan.html", user=admin)
