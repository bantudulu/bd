import pytest


async def mobile_login(client, seeded_data):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seeded_data["customer_a"]["email"],
            "password": seeded_data["passwords"]["customer"],
            "device_id": "phase11-device-001",
            "device_name": "Android Integration Test",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.asyncio
async def test_mobile_login_refresh_rotation_and_logout(client, seeded_data):
    login = await mobile_login(client, seeded_data)
    access = login["access_token"]
    old_refresh = login["refresh_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["id"] == seeded_data["customer_a"]["id"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()["data"]
    assert new_tokens["refresh_token"] != old_refresh

    replay_old_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert replay_old_refresh.status_code == 401
    assert replay_old_refresh.json()["error"]["code"] == "unauthorized"

    new_access = new_tokens["access_token"]
    logged_out = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert logged_out.status_code == 200

    after_logout = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_mobile_order_requires_idempotency_key(client, seeded_data):
    login = await mobile_login(client, seeded_data)
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    payload = {
        "layanan_id": seeded_data["service_id"],
        "varian_id": seeded_data["variant_id"],
        "jadwal": seeded_data["tomorrow"],
        "jam": "16:00",
        "alamat": "Jl. Android Test No. 9",
        "durasi": 1,
        "metode_pembayaran": "cod",
        "form_data": {},
    }

    response = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_mobile_order_retry_is_idempotent(client, seeded_data):
    login = await mobile_login(client, seeded_data)
    headers = {
        "Authorization": f"Bearer {login['access_token']}",
        "Idempotency-Key": "phase11-order-key-0001",
    }
    payload = {
        "layanan_id": seeded_data["service_id"],
        "varian_id": seeded_data["variant_id"],
        "jadwal": seeded_data["tomorrow"],
        "jam": "16:30",
        "alamat": "Jl. Android Idempotency No. 10",
        "durasi": 2,
        "metode_pembayaran": "cod",
        "form_data": {},
        "addon_total": 8_000_000,
    }

    first = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["ok"] is True
    assert first_body["data"]["total_harga"] == 100_000
    assert first_body["meta"]["idempotent_replay"] is False
    first_id = first_body["data"]["id"]

    replay = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert replay.status_code == 201
    replay_body = replay.json()
    assert replay_body["data"]["id"] == first_id
    assert replay_body["meta"]["idempotent_replay"] is True

    changed_payload = dict(payload)
    changed_payload["alamat"] = "Jl. Payload Berbeda No. 99"
    conflict = await client.post("/api/v1/orders", json=changed_payload, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"

    orders = await client.get("/api/v1/orders", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert orders.status_code == 200
    created = [row for row in orders.json()["data"] if row["id"] == first_id]
    assert len(created) == 1
