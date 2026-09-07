from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

load_dotenv()

from app.auth import get_user_from_request
from app.config import (
    ENABLE_CATALOG_SYNC,
    ENABLE_DEMO_SEED,
    IS_PRODUCTION,
    STARTUP_DB_INIT,
)
from app.database import init_db
from app.final_catalog import ensure_final_catalog
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production startup must be read-mostly.
    # Schema migration and seed are explicit operations.
    if STARTUP_DB_INIT:
        await init_db()

    if ENABLE_DEMO_SEED:
        await seed_data()

    if ENABLE_CATALOG_SYNC:
        try:
            await ensure_final_catalog()
        except Exception as exc:
            print(
                "[startup] final catalog sync skipped: "
                f"{type(exc).__name__}: {exc}"
            )

    yield


app = FastAPI(title="BantuDulu", lifespan=lifespan)

# Keep production payload compression from the performance hotfix.
app.add_middleware(
    GZipMiddleware,
    minimum_size=500,
    compresslevel=6,
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


@app.middleware("http")
async def security_and_user_context(
    request: Request,
    call_next,
):
    user = get_user_from_request(request)
    request.state.user = user

    response = await call_next(request)

    path = request.url.path

    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff",
    )
    response.headers.setdefault(
        "X-Frame-Options",
        "DENY",
    )
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(self), payment=()",
    )

    if (
        path.startswith("/api/")
        or user
        or path
        in {
            "/masuk",
            "/daftar",
            "/daengadmin",
            "/loading",
        }
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"

    # Preserve immutable caching from performance hotfix.
    if path.startswith("/static/perf/"):
        response.headers[
            "Cache-Control"
        ] = "public, max-age=31536000, immutable"

    if IS_PRODUCTION:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

    return response


# Legacy api_pesanan router intentionally remains disabled.
from app.routers import (
    admin,
    api,
    auth,
    customer,
    final_api,
    final_pages,
    operational,
    operational_pages,
)

app.include_router(operational_pages.router)
app.include_router(operational.router)
app.include_router(final_pages.router)
app.include_router(final_api.router)
app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(admin.router)
app.include_router(api.router)


@app.get("/sw.js")
async def service_worker():
    from starlette.responses import FileResponse

    return FileResponse(
        "app/static/sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
        },
    )


@app.get("/manifest.json")
async def manifest():
    from starlette.responses import FileResponse

    return FileResponse(
        "app/static/manifest.json",
        media_type="application/json",
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/")
async def root():
    return RedirectResponse(url="/loading")
