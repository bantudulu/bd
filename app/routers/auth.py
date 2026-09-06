from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth import clear_auth_cookie
from app.config import GOOGLE_CLIENT_ID, TURNSTILE_SITE_KEY
from app.templates import render

router = APIRouter(tags=["auth-pages"])


def _auth_context():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "turnstile_site_key": TURNSTILE_SITE_KEY,
    }


@router.get("/masuk")
async def login_page(request: Request):
    if request.state.user:
        return RedirectResponse(url="/beranda")
    return render("auth/login.html", **_auth_context())


@router.get("/daftar")
async def register_page(request: Request):
    if request.state.user:
        return RedirectResponse(url="/beranda")
    return render("auth/register.html", **_auth_context())


@router.get("/daengadmin")
async def daengadmin_page(request: Request):
    if request.state.user and request.state.user.get("role") == "ADMIN":
        return RedirectResponse(url="/admin/dashboard")
    return render("auth/daengadmin.html", **_auth_context())


@router.get("/keluar")
async def logout():
    response = RedirectResponse(url="/masuk")
    clear_auth_cookie(response)
    response.headers["Clear-Site-Data"] = '"cache"'
    return response
