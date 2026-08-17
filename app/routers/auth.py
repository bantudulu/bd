from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone

from app.templates import render
from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_token

# ── Rate Limiter (in-memory) ──
from collections import defaultdict
_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def check_rate_limit(ip: str) -> dict:
    now = datetime.now(timezone.utc).timestamp()
    # Bersihkan entries lama
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOCKOUT_MINUTES * 60]
    attempts = len(_login_attempts[ip])
    remaining = max(0, MAX_ATTEMPTS - attempts)
    if attempts >= MAX_ATTEMPTS:
        return {"allowed": False, "remaining": 0}
    return {"allowed": True, "remaining": remaining}

router = APIRouter(tags=["auth"])

class LoginBody(BaseModel):
    email: str
    password: str

class RegisterBody(BaseModel):
    nama: str
    email: str
    no_hp: str
    password: str

@router.get("/masuk")
async def login_page(request: Request):
    if request.state.user:
        return RedirectResponse(url="/beranda")
    return render("auth/login.html")

@router.get("/daftar")
async def register_page(request: Request):
    if request.state.user:
        return RedirectResponse(url="/beranda")
    return render("auth/register.html")

@router.get("/daengadmin")
async def daengadmin_page(request: Request):
    if request.state.user and request.state.user.get("role") == "ADMIN":
        return RedirectResponse(url="/admin/dashboard")
    return render("auth/daengadmin.html")

@router.get("/api/auth/me")
async def auth_me(request: Request):
    from fastapi.responses import JSONResponse
    user = request.state.user
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return JSONResponse({
        "id": user.get("id"),
        "email": user.get("email"),
        "nama": user.get("nama"),
        "role": user.get("role"),
    })

@router.post("/api/auth/login")
async def login(
    body: LoginBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limiting by IP
    client_ip = request.client.host if request.client else "unknown"
    rate = check_rate_limit(client_ip)
    if not rate["allowed"]:
        return JSONResponse({"error": f"Terlalu banyak percobaan. Coba lagi dalam {LOCKOUT_MINUTES} menit."}, status_code=429)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password):
        _login_attempts[client_ip].append(datetime.now(timezone.utc).timestamp())
        return JSONResponse({"error": "Email atau password salah"}, status_code=401)
    # Login sukses — bersihkan attempts
    _login_attempts.pop(client_ip, None)
    token = create_token({"id": user.id, "email": user.email, "nama": user.nama, "role": user.role})
    resp = JSONResponse({"redirect": "/beranda"}, status_code=200)
    resp.set_cookie(key="token", value=token, httponly=True, secure=True, samesite="lax", max_age=86400)
    return resp

@router.post("/api/auth/register")
async def register(
    body: RegisterBody,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        return JSONResponse({"error": "Email sudah terdaftar"}, status_code=400)
    user = User(
        nama=body.nama,
        email=body.email,
        no_hp=body.no_hp,
        password=hash_password(body.password),
        role="CUSTOMER",
    )
    db.add(user)
    await db.commit()
    token = create_token({"id": user.id, "email": user.email, "nama": user.nama, "role": user.role})
    resp = JSONResponse({"redirect": "/beranda"}, status_code=200)
    resp.set_cookie(key="token", value=token, httponly=True, secure=True, max_age=86400)
    return resp

@router.get("/keluar")
async def logout():
    resp = RedirectResponse(url="/masuk")
    resp.delete_cookie("token")
    return resp
