from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    # Local/dev convenience only. Production should use Alembic migrations.
    from app.models import (  # noqa: F401
        Alamat,
        ExternalIdentity,
        FormField,
        Kategori,
        Layanan,
        LayananVarian,
        Mitra,
        MitraLayanan,
        Notifikasi,
        OrderStatusHistory,
        PaymentTransaction,
        PenugasanMitra,
        Pesanan,
        User,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
