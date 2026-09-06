from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Load .env file (jika ada)
load_dotenv()

from app.config import SECRET_KEY
from app.database import init_db
from app.auth import get_user_from_request
from app.seed import seed_data
from app.final_catalog import ensure_final_catalog

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_data()
    await ensure_final_catalog()
    yield

app = FastAPI(title="BantuDulu", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.middleware("http")
async def add_user_context(request: Request, call_next):
    user = get_user_from_request(request)
    request.state.user = user
    response = await call_next(request)
    return response

# Import routes AFTER app creation
from app.routers import final_pages, final_api, auth, customer, admin, api, api_pesanan

app.include_router(final_pages.router)
app.include_router(final_api.router)
app.include_router(auth.router)
app.include_router(customer.router)
app.include_router(admin.router)
app.include_router(api.router)
app.include_router(api_pesanan.router)

@app.get("/sw.js")
async def service_worker():
    from starlette.responses import FileResponse
    return FileResponse("app/static/sw.js", media_type="application/javascript")

@app.get("/manifest.json")
async def manifest():
    from starlette.responses import FileResponse
    return FileResponse("app/static/manifest.json", media_type="application/json")

@app.get("/")
async def root():
    return RedirectResponse(url="/masuk")
