import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "staging", "production"}:
    raise RuntimeError("APP_ENV harus development, test, staging, atau production.")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY tidak ditemukan. Set melalui environment variable atau file .env lokal.")
if APP_ENV == "production" and len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY production harus minimal 32 karakter.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
APP_NAME = "BantuDulu"
APP_DESC = "Platform Jasa On-Demand"
ENABLE_DEV_SEED = os.getenv("ENABLE_DEV_SEED", "false").strip().lower() in {"1", "true", "yes", "on"}

# Database
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE == "mysql":
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASS = os.getenv("MYSQL_PASS")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DB = os.getenv("MYSQL_DB")

    missing = [
        name
        for name, value in {
            "MYSQL_USER": MYSQL_USER,
            "MYSQL_PASS": MYSQL_PASS,
            "MYSQL_DB": MYSQL_DB,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Konfigurasi MySQL belum lengkap: {', '.join(missing)}")

    DATABASE_URL = (
        f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )
else:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BASE_DIR}/bantudulu_v2.db",
    )

# Explicit DATABASE_URL always wins.
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.environ["DATABASE_URL"]

if APP_ENV == "production":
    if ENABLE_DEV_SEED:
        raise RuntimeError("ENABLE_DEV_SEED tidak boleh aktif di production.")
    scheme = urlparse(DATABASE_URL).scheme.lower()
    if scheme.startswith("sqlite"):
        raise RuntimeError("SQLite tidak diizinkan untuk production. Gunakan database server production.")
    if not scheme.startswith("mysql"):
        raise RuntimeError("Production saat ini hanya mendukung DATABASE_URL MySQL/MariaDB async.")
