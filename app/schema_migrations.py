from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.database import Base, engine

LATEST_SCHEMA_VERSION = 1


def _load_all_models() -> None:
    # Ensure every SQLAlchemy table is registered in Base.metadata.
    from app import models as _models  # noqa: F401
    from app import models_mobile as _models_mobile  # noqa: F401
    from app import models_push as _models_push  # noqa: F401


async def _ensure_version_table(conn) -> None:
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at VARCHAR(40) NOT NULL
            )
            """
        )
    )


async def current_schema_version() -> int:
    async with engine.begin() as conn:
        await _ensure_version_table(conn)
        result = await conn.execute(text("SELECT MAX(version) FROM schema_migrations"))
        return int(result.scalar() or 0)


async def run_migrations() -> int:
    """Apply repository-owned schema migrations up to LATEST_SCHEMA_VERSION.

    Version 1 is the baseline for the hardened BantuDulu schema. On an existing
    compatible database, SQLAlchemy create_all is intentionally non-destructive:
    it creates only missing tables/indexes before recording the baseline version.
    Future schema changes must be introduced as a new explicit version here rather
    than relying on application startup to mutate production schema.
    """
    _load_all_models()

    async with engine.begin() as conn:
        await _ensure_version_table(conn)
        result = await conn.execute(text("SELECT MAX(version) FROM schema_migrations"))
        version = int(result.scalar() or 0)

        if version > LATEST_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} lebih baru dari aplikasi ({LATEST_SCHEMA_VERSION})."
            )

        if version < 1:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:version, :applied_at)"),
                {
                    "version": 1,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            version = 1

    return version


async def assert_schema_current() -> int:
    version = await current_schema_version()
    if version != LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            "Database schema belum siap untuk aplikasi ini. "
            f"Current={version}, required={LATEST_SCHEMA_VERSION}. "
            "Jalankan `python -m scripts.migrate` sebelum menyalakan web service."
        )
    return version
