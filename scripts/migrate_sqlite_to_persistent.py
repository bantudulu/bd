import asyncio
import os
from pathlib import Path

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import DATABASE_URL, USING_SQLITE
from app.database import Base, engine as target_engine
from app.models import (
    Alamat,
    FormField,
    Kategori,
    Layanan,
    LayananVarian,
    Notifikasi,
    Pesanan,
    User,
)

CORE_MODELS = [
    User,
    Alamat,
    Kategori,
    Layanan,
    LayananVarian,
    FormField,
    Pesanan,
    Notifikasi,
]


async def main():
    if USING_SQLITE:
        raise SystemExit("TARGET DATABASE_URL masih SQLite. Set DATABASE_URL persistent terlebih dahulu.")

    default_source = Path(__file__).resolve().parents[1] / "app" / "bantudulu_v2.db"
    source_url = os.getenv("SOURCE_DATABASE_URL", f"sqlite+aiosqlite:///{default_source}")
    if not source_url.startswith("sqlite+"):
        raise SystemExit("SOURCE_DATABASE_URL harus menunjuk SQLite sumber.")

    source_engine = create_async_engine(source_url)
    SourceSession = async_sessionmaker(source_engine, expire_on_commit=False)

    # Create the complete current schema on the empty persistent target.
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TargetSession = async_sessionmaker(target_engine, expire_on_commit=False)
    async with TargetSession() as target:
        existing = (await target.execute(select(func.count()).select_from(User))).scalar_one()
        if existing:
            raise SystemExit("Target database tidak kosong. Migrasi dihentikan untuk mencegah duplikasi.")

    async with SourceSession() as source, TargetSession() as target:
        total = 0
        for model in CORE_MODELS:
            rows = (await source.execute(select(model))).scalars().all()
            for row in rows:
                data = {column.name: getattr(row, column.name) for column in model.__table__.columns}
                await target.execute(insert(model.__table__).values(**data))
            await target.commit()
            total += len(rows)
            print(f"{model.__tablename__}: {len(rows)} rows")
        print(f"MIGRATION COMPLETE: {total} rows")

    await source_engine.dispose()
    await target_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
