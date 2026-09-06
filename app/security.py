from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any

import httpx
from fastapi import HTTPException, Request

from app.config import (
    GOOGLE_CLIENT_ID,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    TURNSTILE_ENABLED,
    TURNSTILE_SECRET_KEY,
)


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> list[float]:
        now = time.time()
        values = [t for t in self._attempts.get(key, []) if now - t < self.window_seconds]
        if values:
            self._attempts[key] = values
        else:
            self._attempts.pop(key, None)
        return values

    def allowed(self, key: str) -> bool:
        return len(self._prune(key)) < self.max_attempts

    def hit(self, key: str) -> None:
        self._prune(key)
        self._attempts[key].append(time.time())

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)


login_limiter = SlidingWindowLimiter(LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)
register_limiter = SlidingWindowLimiter(max(3, LOGIN_MAX_ATTEMPTS), LOGIN_WINDOW_SECONDS)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def auth_rate_key(request: Request, identity: str) -> str:
    normalized = re.sub(r"\s+", "", (identity or "").casefold())
    return f"{client_ip(request)}:{normalized}"


def reject_honeypot(value: Any) -> None:
    if str(value or "").strip():
        raise HTTPException(status_code=400, detail="Permintaan tidak valid")


async def verify_turnstile(token: str | None, request: Request) -> None:
    if not TURNSTILE_ENABLED:
        return
    if not token:
        raise HTTPException(status_code=400, detail="Verifikasi keamanan belum selesai")

    payload = {
        "secret": TURNSTILE_SECRET_KEY,
        "response": token,
        "remoteip": client_ip(request),
    }
    try:
        async with httpx.AsyncClient(timeout=7.0) as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=payload,
            )
        data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Layanan verifikasi keamanan sedang tidak tersedia") from exc

    if not data.get("success"):
        raise HTTPException(status_code=400, detail="Verifikasi keamanan gagal. Silakan coba lagi.")


async def verify_google_credential(credential: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Login Google belum dikonfigurasi")
    if not credential:
        raise HTTPException(status_code=400, detail="Credential Google tidak ditemukan")

    try:
        async with httpx.AsyncClient(timeout=7.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Login Google tidak valid")
        data = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Google Identity sedang tidak tersedia") from exc

    if data.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Audience Google tidak valid")

    if data.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Issuer Google tidak valid")

    if str(data.get("email_verified", "")).lower() not in {"true", "1"}:
        raise HTTPException(status_code=401, detail="Email Google belum terverifikasi")

    email = str(data.get("email") or "").strip().lower()
    subject = str(data.get("sub") or "").strip()
    if not email or not subject:
        raise HTTPException(status_code=401, detail="Identitas Google tidak lengkap")

    return {
        "sub": subject,
        "email": email,
        "name": str(data.get("name") or email.split("@", 1)[0]).strip(),
        "picture": str(data.get("picture") or "").strip(),
    }
