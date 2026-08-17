from datetime import datetime, timezone

from app.mobile_auth import (
    create_mobile_access_token,
    decode_mobile_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_expiry,
)
from app.routers.api_pesanan import CreatePesananBody
from app.routers.mobile_v1 import _request_fingerprint


def test_mobile_access_token_contract():
    token = create_mobile_access_token(
        user_id="user123",
        email="user@example.com",
        nama="User Test",
        role="CUSTOMER",
        session_id="sess123",
    )
    payload = decode_mobile_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user123"
    assert payload["sid"] == "sess123"
    assert payload["typ"] == "access"
    assert payload["role"] == "CUSTOMER"


def test_refresh_token_is_opaque_and_hash_is_deterministic():
    token = generate_refresh_token()
    assert len(token) >= 32
    hashed = hash_refresh_token(token)
    assert len(hashed) == 64
    assert hashed == hash_refresh_token(token)
    assert token != hashed


def test_refresh_expiry_is_future_utc():
    expiry = refresh_expiry()
    assert expiry.tzinfo is not None
    assert expiry > datetime.now(timezone.utc)


def _order_body(**overrides):
    data = {
        "layanan_id": "layanan001",
        "varian_id": "varian0001",
        "jadwal": "2026-12-20",
        "jam": "10:00",
        "alamat": "Jl. Contoh No. 1, Makassar",
        "durasi": 1,
        "metode_pembayaran": "cod",
        "catatan": None,
        "form_data": {},
    }
    data.update(overrides)
    return CreatePesananBody(**data)


def test_idempotency_fingerprint_same_payload_same_hash():
    first = _order_body()
    second = _order_body()
    assert _request_fingerprint(first) == _request_fingerprint(second)


def test_idempotency_fingerprint_changes_with_payload():
    first = _order_body()
    second = _order_body(alamat="Jl. Berbeda No. 9, Makassar")
    assert _request_fingerprint(first) != _request_fingerprint(second)
