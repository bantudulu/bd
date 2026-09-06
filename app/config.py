import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "BantuDulu"
APP_DESC = "Platform Jasa On-Demand"
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production" or bool(os.getenv("VERCEL"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY tidak ditemukan. Set di environment variable atau .env lokal.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
JWT_ISSUER = os.getenv("JWT_ISSUER", "BantuDulu")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "bantudulu-web")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if IS_PRODUCTION else "0").strip().lower() in {"1", "true", "yes", "on"}

# ── Database ──
# Production should set DATABASE_URL to persistent PostgreSQL/MySQL.
# Local development may keep SQLite.
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Common provider URLs are synchronous by default. Normalize to async drivers.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgres://"):]
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgresql://"):]
    elif DATABASE_URL.startswith("mysql://"):
        DATABASE_URL = "mysql+aiomysql://" + DATABASE_URL[len("mysql://"):]

    # Neon/libpq URLs commonly include sslmode=require and
    # channel_binding=require. SQLAlchemy asyncpg forwards URL query
    # parameters to asyncpg, which expects "ssl", not "sslmode", and
    # does not accept channel_binding as a connect argument.
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(DATABASE_URL)
        query = []

        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "channel_binding":
                continue
            if key == "sslmode":
                key = "ssl"
            query.append((key, value))

        DATABASE_URL = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )
elif DB_ENGINE == "mysql":
    MYSQL_USER = os.getenv("MYSQL_USER", "bantudulu_admin")
    MYSQL_PASS = os.getenv("MYSQL_PASS", "")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DB = os.getenv("MYSQL_DB", "bantudulu_db")
    DATABASE_URL = f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
else:
    DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'bantudulu_v2.db'}"

USING_SQLITE = DATABASE_URL.startswith("sqlite+")

def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# Startup mutations are allowed locally, but disabled by default on Vercel/production.
STARTUP_DB_INIT = env_bool("STARTUP_DB_INIT", not IS_PRODUCTION)
ENABLE_DEMO_SEED = env_bool("ENABLE_DEMO_SEED", not IS_PRODUCTION)
ENABLE_CATALOG_SYNC = env_bool("ENABLE_CATALOG_SYNC", not IS_PRODUCTION)

# New marketplace tables are opt-in until Alembic migration has been applied.
MARKETPLACE_SCHEMA_ENABLED = env_bool("MARKETPLACE_SCHEMA_ENABLED", False)

# ── Human verification / Google Identity ──
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "").strip()
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
TURNSTILE_ENABLED = bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)

LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))

# ── Payment availability ──
# COD is available now. Bank/QRIS stay disabled until a real gateway/reconciliation flow exists.
PAYMENT_BANK_ENABLED = env_bool("PAYMENT_BANK_ENABLED", False)
PAYMENT_QRIS_ENABLED = env_bool("PAYMENT_QRIS_ENABLED", False)
