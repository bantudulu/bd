from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from sqlalchemy import select, text

load_dotenv()

from app.auth import get_user_from_request
from app.config import APP_ENV, ENABLE_DEV_SEED, SECRET_KEY
from app.database import async_session, init_db
from app.models import Pesanan, User
from app.schema_migrations import LATEST_SCHEMA_VERSION, assert_schema_current
from app.seed import seed_data

LEGACY_DEMO_EMAILS = {"admin@bantudulu.id", "user@bantudulu.id"}


async def _assert_no_legacy_demo_accounts():
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
    if APP_ENV == "production":
        if ENABLE_DEV_SEED:
            raise RuntimeError("ENABLE_DEV_SEED tidak boleh aktif di production.")
        # Production schema changes must happen as a deployment step, never implicitly
        # while the web process is starting.
        await assert_schema_current()
    else:
        await init_db()
        if ENABLE_DEV_SEED:
            await seed_data()

    await _assert_no_legacy_demo_accounts()
    yield


app = FastAPI(title="BantuDulu", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=APP_ENV == "production", same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health/live", include_in_schema=False)
async def health_live():
    return {"ok": True, "service": "bantudulu", "status": "live"}


@app.get("/health/ready", include_in_schema=False)
async def health_ready():
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        if APP_ENV == "production":
            version = await assert_schema_current()
        else:
            version = LATEST_SCHEMA_VERSION
    except Exception:
        return JSONResponse(
            {"ok": False, "service": "bantudulu", "status": "not_ready"},
            status_code=503,
        )
    return {
        "ok": True,
        "service": "bantudulu",
        "status": "ready",
        "schema_version": version,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v1/"):
        code = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limited",
        }.get(exc.status_code, "request_error")
        return JSONResponse(
            {"ok": False, "error": {"code": code, "message": str(exc.detail)}},
            status_code=exc.status_code,
            headers=exc.headers,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/v1/"):
        fields = []
        for item in exc.errors():
            loc = [str(part) for part in item.get("loc", []) if part not in {"body", "query", "path", "header"}]
            fields.append({"field": ".".join(loc) or None, "message": item.get("msg", "Invalid value")})
        return JSONResponse(
            {"ok": False, "error": {"code": "validation_error", "message": "Data request tidak valid.", "fields": fields}},
            status_code=422,
        )
    return JSONResponse({"detail": exc.errors()}, status_code=422)


async def _get_order_for_access(identifier: str):
    async with async_session() as db:
        result = await db.execute(select(Pesanan).where((Pesanan.id == identifier) | (Pesanan.kode == identifier)))
        return result.scalar_one_or_none()


@app.middleware("http")
async def security_and_user_context(request: Request, call_next):
    user = get_user_from_request(request)
    request.state.user = user
    path = request.url.path
    method = request.method.upper()

    if method == "GET" and path == "/api/pesanan":
        if not user or user.get("role") != "ADMIN":
            return JSONResponse({"detail": "Akses ditolak."}, status_code=403 if user else 401)

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


from app.routers import admin, admin_assignment, api, api_pesanan, auth, customer, mobile_v1, notification_pages, notifications

app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(notification_pages.router)
app.include_router(admin.router)
app.include_router(api.router)
app.include_router(api_pesanan.router)
app.include_router(admin_assignment.router)
app.include_router(notifications.router)
app.include_router(mobile_v1.router)


@app.get("/sw.js")
async def service_worker():
    from starlette.responses import FileResponse
    return FileResponse("app/static/sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.json")
async def manifest():
    from starlette.responses import FileResponse
    return FileResponse("app/static/manifest.json", media_type="application/json")


@app.get("/")
async def root():
    return RedirectResponse(url="/masuk")
