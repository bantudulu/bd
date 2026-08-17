import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY tidak ditemukan. Set di .env atau environment variable.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
APP_NAME = "BantuDulu"
APP_DESC = "Platform Jasa On-Demand"

# ── Database ──
# Default: SQLite. Set DB_ENGINE=mysql to use MariaDB.
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite")

if DB_ENGINE == "mysql":
    MYSQL_USER = os.getenv("MYSQL_USER", "bantudulu_admin")
    MYSQL_PASS = os.getenv("MYSQL_PASS", "bantuduluSQL")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3307")
    MYSQL_DB = os.getenv("MYSQL_DB", "bantudulu_db")
    DATABASE_URL = f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/bantudulu_v2.db")

# Allow explicit override
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
