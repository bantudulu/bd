import pytest


@pytest.mark.asyncio
async def test_customer_to_admin_release_rehearsal(client, seeded_data, legacy_auth_headers):
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seeded_data["customer_a"]["email"],
            "password": seeded_data["passwords"]["customer"],
            "device_id": "phase13-rehearsal-device",
            "device_name": "Release Rehearsal Android",
        },
    )
    assert login.status_code == 200
    access = login.json()["data"]["access_token"]
    customer_headers = {
        "Authorization": f"Bearer {access}",
        "Idempotency-Key": "phase13-release-order-001",
    }

    created = await client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "layanan_id": seeded_data["service_id"],
            "varian_id": seeded_data["variant_id"],
            "jadwal": seeded_data["tomorrow"],
            "jam": "17:00",
            "alamat": "Jl. Release Rehearsal No. 13",
            "durasi": 1,
            "metode_pembayaran": "cod",
            "form_data": {},
        },
    )
    assert created.status_code == 201
    order = created.json()["data"]
    assert order["status"] == "menunggu"

    admin_headers = legacy_auth_headers(seeded_data["admin"])
    assigned = await client.post(
        f"/api/admin/pesanan/{order['kode']}/assign",
        headers=admin_headers,
        json={"petugas_id": seeded_data["worker_a_id"]},
    )
    assert assigned.status_code == 200

    for next_status in ("menuju_lokasi", "dimulai", "selesai"):
        response = await client.put(
            f"/api/admin/operasional/pesanan/{order['kode']}/status",
            headers=admin_headers,
            json={"status": next_status},
        )
        assert response.status_code == 200

    detail = await client.get(
        f"/api/v1/orders/{order['kode']}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "selesai"
    assert detail.json()["data"]["assignment"]["petugas"]["id"] == seeded_data["worker_a_id"]

    notifications = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert notifications.status_code == 200
    rows = notifications.json()["data"]
    assert any(row["order_code"] == order["kode"] for row in rows)
