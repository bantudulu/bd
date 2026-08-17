import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import JWT_ALGORITHM, SECRET_KEY

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30


def create_mobile_access_token(*, user_id: str, email: str, nama: str, role: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "id": user_id,
        "email": email,
        "nama": nama,
        "role": role,
        "sid": session_id,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_mobile_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("typ") != "access" or not payload.get("sid") or not payload.get("sub"):
        return None
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)
