import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Request
from jose import JWTError, jwt

from app.config import (
    COOKIE_SECURE,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_EXPIRY_HOURS,
    JWT_ISSUER,
    SECRET_KEY,
)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(data: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = data.copy()
    payload.update(
        {
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "jti": uuid.uuid4().hex,
        }
    )
    return jwt.encode(claims=payload, key=SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token=token,
            key=SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except JWTError:
        return None


def get_user_from_request(request: Request):
    token = request.cookies.get("token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        return None
    return decode_token(token)


def set_auth_cookie(response, token: str) -> None:
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    response.delete_cookie("token", path="/", secure=COOKIE_SECURE, samesite="lax")
