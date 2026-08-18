import pytest


@pytest.mark.asyncio
async def test_order_list_requires_admin(client, seeded_data, legacy_auth_headers):
    anonymous = await client.get("/api/pesanan")
    assert anonymous.status_code == 401

    customer = await client.get(
        "/api/pesanan",
        headers=legacy_auth_headers(seeded_data["customer_a"]),
    )
    assert customer.status_code == 403

    admin = await client.get(
        "/api/pesanan?limit=10&offset=0",
        headers=legacy_auth_headers(seeded_data["admin"]),
    )
    assert admin.status_code == 200
    assert len(admin.json()) == 2


@pytest.mark.asyncio
async def test_customer_cannot_read_another_customers_order(client, seeded_data, legacy_auth_headers):
    headers = legacy_auth_headers(seeded_data["customer_a"])

    api_response = await client.get(
        f"/api/pesanan/{seeded_data['order_b_code']}",
        headers=headers,
    )
    assert api_response.status_code == 403

    page_response = await client.get(
        f"/pesanan/{seeded_data['order_b_code']}",
        headers=headers,
    )
    assert page_response.status_code == 403

    own_response = await client.get(
        f"/api/pesanan/{seeded_data['order_a_code']}",
        headers=headers,
    )
    assert own_response.status_code == 200
    assert own_response.json()["kode"] == seeded_data["order_a_code"]


@pytest.mark.asyncio
async def test_server_ignores_client_addon_total(client, seeded_data, legacy_auth_headers):
    payload = {
        "layanan_id": seeded_data["service_id"],
        "varian_id": seeded_data["variant_id"],
        "jadwal": seeded_data["tomorrow"],
        "jam": "14:00",
        "alamat": "Jl. Pricing Test No. 10",
        "durasi": 2,
        "metode_pembayaran": "cod",
        "form_data": {},
        "addon_total": 9_999_999,
    }

    response = await client.post(
        "/api/pesanan",
        json=payload,
        headers=legacy_auth_headers(seeded_data["customer_a"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total_harga"] == 100_000


@pytest.mark.asyncio
async def test_variant_must_belong_to_selected_service(client, seeded_data, legacy_auth_headers):
    payload = {
        "layanan_id": seeded_data["service_id"],
        "varian_id": seeded_data["other_variant_id"],
        "jadwal": seeded_data["tomorrow"],
        "jam": "15:00",
        "alamat": "Jl. Variant Mismatch No. 20",
        "durasi": 1,
        "metode_pembayaran": "cod",
        "form_data": {},
    }

    response = await client.post(
        "/api/pesanan",
        json=payload,
        headers=legacy_auth_headers(seeded_data["customer_a"]),
    )
    assert response.status_code == 400
    assert "Varian tidak sesuai" in response.json()["detail"]
