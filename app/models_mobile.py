from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import gen_id, utcnow


class MobileSession(Base):
    """Revocable Android/mobile session. Refresh tokens are stored only as SHA-256 hashes."""
    __tablename__ = "mobile_sessions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class OrderIdempotency(Base):
    """Persists Android order request keys so network retries cannot duplicate an order."""
    __tablename__ = "order_idempotency"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_order_idempotency_user_key"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    # Nullable while a request owns the key but has not completed yet.
    pesanan_id: Mapped[str | None] = mapped_column(ForeignKey("pesanan.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
