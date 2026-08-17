from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from sqlalchemy import select

# Load local .env only when present. Production should inject env vars externally.
load_dotenv()

from app.auth import get_user_from_request
from app.config import APP_ENV, ENABLE_DEV_SEED, SECRET_KEY
from app.database import async_session, init_db
from app.models import Pesanan, User
from app.seed import seed_data

LEGACY_DEMO_EMAILS = {
    "admin@bantudulu.id",
    "user@bantudulu.id",
}


async def _assert_no_legacy_demo_accounts():
    """Refuse production startup while known public demo accounts still exist."""
    if APP_ENV != "production":
        return

    async with async_session() as db:
        result = await db.execute(select(User.email).where(User.email.in_(LEGACY_DEMO_EMAILS)))
        exposed_accounts = sorted(result.scalars().all())

    if exposed_accounts:
        accounts = ", ".join(exposed_accounts)
        raise RuntimeError(
            "Production diblokir karena database masih memiliki akun demo/default yang "
            f"credential lamanya pernah dipublikasikan: {accounts}. "
            "Hapus akun demo tersebut atau reset credential admin secara aman sebelum startup."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    if APP_ENV == "production" and ENABLE_DEV_SEED:
        raise RuntimeError("ENABLE_DEV_SEED tidak boleh aktif di production.")

    if ENABLE_DEV_SEED:
        await seed_data()

    await _assert_no_legacy_demo_accounts()
    yield


app = FastAPI(title="BantuDulu", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=APP_ENV == "production",
    same_site="lax",
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


async def _get_order_for_access(identifier: str):
    async with async_session() as db:
        result = await db.execute(
            select(Pesanan).where(
                (Pesanan.id == identifier) | (Pesanan.kode == identifier)
            )
        )
        return result.scalar_one_or_none()


@app.middleware("http")
async def security_and_user_context(request: Request, call_next):
    user = get_user_from_request(request)
    request.state.user = user

    path = request.url.path
    method = request.method.upper()

    # Sensitive order APIs must never be anonymous.
    if method == "GET" and path == "/api/pesanan":
        if not user or user.get("role") != "ADMIN":
            return JSONResponse(
                {"detail": "Akses ditolak."},
                status_code=403 if user else 401,
            )

    # Order detail API: admin may access all, customer only owns their order.
    if method == "GET" and path.startswith("/api/pesanan/") and path != "/api/pesanan/aktif":
        if not user:
            return JSONResponse({"detail": "Silakan login."}, status_code=401)

        identifier = path.removeprefix("/api/pesanan/").strip("/")
        if identifier:
            order = await _get_order_for_access(identifier)
            if not order:
                return JSONResponse({"detail": "Pesanan tidak ditemukan."}, status_code=404)
            if user.get("role") != "ADMIN" and order.user_id != user.get("id"):
                return JSONResponse({"detail": "Akses ditolak."}, status_code=403)

    # Customer order detail page: require login and ownership.
    if method == "GET" and path.startswith("/pesanan/"):
        if not user:
            return RedirectResponse(url="/masuk", status_code=302)

        identifier = path.removeprefix("/pesanan/").strip("/")
        if identifier:
            order = await _get_order_for_access(identifier)
            if not order:
                return JSONResponse({"detail": "Pesanan tidak ditemukan."}, status_code=404)
            if user.get("role") != "ADMIN" and order.user_id != user.get("id"):
                return JSONResponse({"detail": "Akses ditolak."}, status_code=403)

    return await call_next(request)


# Import routes AFTER app creation
from app.routers import admin, admin_assignment, api, api_pesanan, auth, customer

app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(admin.router)
app.include_router(api.router)
app.include_router(api_pesanan.router)
app.include_router(admin_assignment.router)


@app.get("/sw.js")
async def service_worker():
    from starlette.responses import FileResponse

    return FileResponse(
        "app/static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/manifest.json")
async def manifest():
    from starlette.responses import FileResponse

    return FileResponse("app/static/manifest.json", media_type="application/json")


@app.get("/")
async def root():
    return RedirectResponse(url="/masuk")