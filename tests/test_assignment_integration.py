import pytest
from sqlalchemy import select

from app.database import async_session
from app.models import Assignment, Notifikasi, Pesanan


@pytest.mark.asyncio
async def test_assignment_creates_history_and_customer_notification(client, seeded_data, legacy_auth_headers):
    response = await client.post(
        f"/api/admin/pesanan/{seeded_data['order_a_code']}/assign",
        json={"petugas_id": seeded_data["worker_a_id"]},
        headers=legacy_auth_headers(seeded_data["admin"]),
    )
    assert response.status_code == 200
    assert response.json()["pesanan"]["status"] == "ditugaskan"
    assert response.json()["assignment"]["petugas_id"] == seeded_data["worker_a_id"]

    async with async_session() as db:
        order = await db.get(Pesanan, seeded_data["order_a_id"])
        assert order.status == "ditugaskan"

        assignment_result = await db.execute(
            select(Assignment).where(
                Assignment.pesanan_id == seeded_data["order_a_id"],
                Assignment.status == "aktif",
            )
        )
        assignment = assignment_result.scalar_one()
        assert assignment.petugas_id == seeded_data["worker_a_id"]

        notification_result = await db.execute(
            select(Notifikasi).where(Notifikasi.pesanan_id == seeded_data["order_a_id"])
        )
        notifications = notification_result.scalars().all()
        assert any("Petugas" in notification.judul for notification in notifications)


@pytest.mark.asyncio
async def test_reassignment_requires_reason(client, seeded_data, legacy_auth_headers):
    headers = legacy_auth_headers(seeded_data["admin"])
    first = await client.post(
        f"/api/admin/pesanan/{seeded_data['order_a_code']}/assign",
        json={"petugas_id": seeded_data["worker_a_id"]},
        headers=headers,
    )
    assert first.status_code == 200

    response = await client.post(
        f"/api/admin/pesanan/{seeded_data['order_a_code']}/assign",
        json={"petugas_id": seeded_data["worker_b_id"]},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Alasan penggantian" in response.json()["detail"]


@pytest.mark.asyncio
async def test_operational_status_cannot_skip_steps_and_reassign_after_start(client, seeded_data, legacy_auth_headers):
    headers = legacy_auth_headers(seeded_data["admin"])
    assigned = await client.post(
        f"/api/admin/pesanan/{seeded_data['order_a_code']}/assign",
        json={"petugas_id": seeded_data["worker_a_id"]},
        headers=headers,
    )
    assert assigned.status_code == 200

    skipped = await client.put(
        f"/api/admin/operasional/pesanan/{seeded_data['order_a_code']}/status",
        json={"status": "dimulai"},
        headers=headers,
    )
    assert skipped.status_code == 409

    toward = await client.put(
        f"/api/admin/operasional/pesanan/{seeded_data['order_a_code']}/status",
        json={"status": "menuju_lokasi"},
        headers=headers,
    )
    assert toward.status_code == 200

    started = await client.put(
        f"/api/admin/operasional/pesanan/{seeded_data['order_a_code']}/status",
        json={"status": "dimulai"},
        headers=headers,
    )
    assert started.status_code == 200

    reassign = await client.post(
        f"/api/admin/pesanan/{seeded_data['order_a_code']}/assign",
        json={
            "petugas_id": seeded_data["worker_b_id"],
            "alasan_penggantian": "Pergantian test setelah mulai",
        },
        headers=headers,
    )
    assert reassign.status_code == 409

    finished = await client.put(
        f"/api/admin/operasional/pesanan/{seeded_data['order_a_code']}/status",
        json={"status": "selesai"},
        headers=headers,
    )
    assert finished.status_code == 200
