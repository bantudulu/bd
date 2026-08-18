import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Test configuration must be present before app modules are imported.
os.environ["APP_ENV"] = "test"
os.environ["ENABLE_DEV_SEED"] = "false"
os.environ["SECRET_KEY"] = "phase-11-test-secret-key-that-is-long-enough-2026"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./.pytest-bantudulu.db"

from app.auth import create_token, hash_password  # noqa: E402
from app.database import Base, async_session, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import Kategori, Layanan, LayananVarian, Pesanan, Petugas, User  # noqa: E402
import app.models_mobile as _models_mobile  # noqa: F401,E402
import app.models_push as _models_push  # noqa: F401,E402


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=False,
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def seeded_data():
    tomorrow = (datetime.now(ZoneInfo("Asia/Makassar")).date() + timedelta(days=1)).isoformat()

    async with async_session() as db:
        admin = User(
            nama="Admin Test",
            email="admin.test@example.com",
            no_hp="081111111111",
            password=hash_password("AdminPass123!"),
            role="ADMIN",
        )
        customer_a = User(
            nama="Customer A",
            email="customer.a@example.com",
            no_hp="082111111111",
            password=hash_password("CustomerPass123!"),
            role="CUSTOMER",
        )
        customer_b = User(
            nama="Customer B",
            email="customer.b@example.com",
            no_hp="082222222222",
            password=hash_password("CustomerPass123!"),
            role="CUSTOMER",
        )
        db.add_all([admin, customer_a, customer_b])
        await db.flush()

        category = Kategori(
            nama="Test Category",
            icon="🧪",
            slug="test-category",
            warna="#042544",
            urutan=1,
        )
        db.add(category)
        await db.flush()

        service = Layanan(
            kategori_id=category.id,
            nama="Test Service",
            deskripsi="Service for integration tests",
            jenis_layanan="bersih_rumah",
            tipe_hitung="per_jam",
            aktif=True,
        )
        other_service = Layanan(
            kategori_id=category.id,
            nama="Other Service",
            deskripsi="Other service for variant mismatch tests",
            jenis_layanan="cuci_ac",
            tipe_hitung="per_pekerjaan",
            aktif=True,
        )
        db.add_all([service, other_service])
        await db.flush()

        variant = LayananVarian(
            layanan_id=service.id,
            nama="Standard",
            harga=50_000,
            deskripsi="Standard test variant",
        )
        other_variant = LayananVarian(
            layanan_id=other_service.id,
            nama="Other Variant",
            harga=75_000,
            deskripsi="Other test variant",
        )
        db.add_all([variant, other_variant])
        await db.flush()

        worker_a = Petugas(
            nama="Petugas A",
            no_hp="083111111111",
            wilayah="Makassar",
            keahlian="Test Service",
            aktif=True,
        )
        worker_b = Petugas(
            nama="Petugas B",
            no_hp="083222222222",
            wilayah="Makassar",
            keahlian="Test Service",
            aktif=True,
        )
        db.add_all([worker_a, worker_b])
        await db.flush()

        order_a = Pesanan(
            user_id=customer_a.id,
            layanan_id=service.id,
            varian_id=variant.id,
            kode="BD-TESTA001",
            status="menunggu",
            alamat="Jl. Customer A No. 1",
            jadwal=tomorrow,
            jam="10:00",
            durasi=1,
            total_harga=50_000,
            form_data='{"metode_pembayaran":"cod"}',
        )
        order_b = Pesanan(
            user_id=customer_b.id,
            layanan_id=service.id,
            varian_id=variant.id,
            kode="BD-TESTB001",
            status="menunggu",
            alamat="Jl. Customer B No. 2",
            jadwal=tomorrow,
            jam="11:00",
            durasi=1,
            total_harga=50_000,
            form_data='{"metode_pembayaran":"cod"}',
        )
        db.add_all([order_a, order_b])
        await db.commit()

        return {
            "admin": {"id": admin.id, "email": admin.email, "nama": admin.nama, "role": admin.role},
            "customer_a": {"id": customer_a.id, "email": customer_a.email, "nama": customer_a.nama, "role": customer_a.role},
            "customer_b": {"id": customer_b.id, "email": customer_b.email, "nama": customer_b.nama, "role": customer_b.role},
            "passwords": {
                "admin": "AdminPass123!",
                "customer": "CustomerPass123!",
            },
            "category_id": category.id,
            "service_id": service.id,
            "variant_id": variant.id,
            "other_service_id": other_service.id,
            "other_variant_id": other_variant.id,
            "worker_a_id": worker_a.id,
            "worker_b_id": worker_b.id,
            "order_a_id": order_a.id,
            "order_a_code": order_a.kode,
            "order_b_id": order_b.id,
            "order_b_code": order_b.kode,
            "tomorrow": tomorrow,
        }


@pytest.fixture
def legacy_auth_headers():
    def build(user: dict) -> dict[str, str]:
        token = create_token(
            {
                "id": user["id"],
                "email": user["email"],
                "nama": user["nama"],
                "role": user["role"],
            }
        )
        return {"Authorization": f"Bearer {token}"}

    return build
