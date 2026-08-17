from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    # Import all mapped models before create_all during development.
    # Production migration flow will replace create_all in the database-hardening phase.
    from app.models import (  # noqa: F401
        Alamat,
        Assignment,
        FormField,
        Kategori,
        Layanan,
        LayananVarian,
        Notifikasi,
        Pesanan,
        Petugas,
        User,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
