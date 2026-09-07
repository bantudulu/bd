import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base

def gen_id():
    return uuid.uuid4().hex[:12]

def utcnow():
    # PostgreSQL schema uses TIMESTAMP WITHOUT TIME ZONE. Keep UTC semantics
    # while returning a naive datetime so asyncpg can bind it safely.
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ── Enums ──

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"

class OrderStatus(str, enum.Enum):
    MENUNGGU = "menunggu"
    DIPROSES = "diproses"
    DITUGASKAN = "ditugaskan"
    MENUJU_LOKASI = "menuju_lokasi"
    DIMULAI = "dimulai"
    SELESAI = "selesai"
    DIBATALKAN = "dibatalkan"

class JenisLayanan(str, enum.Enum):
    BERSIH = "bersih_rumah"
    CUCI_AC = "cuci_ac"
    LES = "les_privat"
    PIJAT = "pijat_relaksasi"
    SALON = "salon"
    MUA = "mua"
    BELANJA = "bantu_belanja"

# ── Models ──

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    nama: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    no_hp: Mapped[str] = mapped_column(String(20))
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER", index=True)
    foto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    alamat: Mapped[list["Alamat"]] = relationship("Alamat", back_populates="user", cascade="all, delete-orphan")
    pesanan: Mapped[list["Pesanan"]] = relationship("Pesanan", back_populates="user", cascade="all, delete-orphan")

class Alamat(Base):
    __tablename__ = "alamat"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(50), default="Rumah")
    alamat_lengkap: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User", back_populates="alamat")

class Kategori(Base):
    __tablename__ = "kategori"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    nama: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(10), default="📦")
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    warna: Mapped[str] = mapped_column(String(7), default="#6366f1")
    urutan: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    layanan: Mapped[list["Layanan"]] = relationship("Layanan", back_populates="kategori", cascade="all, delete-orphan")

class Layanan(Base):
    __tablename__ = "layanan"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    kategori_id: Mapped[str] = mapped_column(ForeignKey("kategori.id"), index=True)
    nama: Mapped[str] = mapped_column(String(100))
    deskripsi: Mapped[str] = mapped_column(Text)
    jenis_layanan: Mapped[str] = mapped_column(String(30))  # reference ke JenisLayanan enum
    tipe_hitung: Mapped[str] = mapped_column(String(20), default="per_jam")  # per_jam, per_unit, per_pekerjaan, per_order
    gambar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    kategori: Mapped["Kategori"] = relationship("Kategori", back_populates="layanan")
    varian: Mapped[list["LayananVarian"]] = relationship("LayananVarian", back_populates="layanan", cascade="all, delete-orphan")
    form_fields: Mapped[list["FormField"]] = relationship("FormField", back_populates="layanan", cascade="all, delete-orphan")
    pesanan: Mapped[list["Pesanan"]] = relationship("Pesanan", back_populates="layanan")

class LayananVarian(Base):
    __tablename__ = "layanan_varian"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    layanan_id: Mapped[str] = mapped_column(ForeignKey("layanan.id"), index=True)
    nama: Mapped[str] = mapped_column(String(100))
    harga: Mapped[int] = mapped_column(Integer)
    deskripsi: Mapped[str | None] = mapped_column(Text, nullable=True)

    layanan: Mapped["Layanan"] = relationship("Layanan", back_populates="varian")
    pesanan: Mapped[list["Pesanan"]] = relationship("Pesanan", back_populates="varian")

class FormField(Base):
    """Dynamic form fields per layanan (e.g., 'Jenis Pembersihan', 'PK AC', 'Jenjang')"""
    __tablename__ = "form_fields"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    layanan_id: Mapped[str] = mapped_column(ForeignKey("layanan.id"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    field_type: Mapped[str] = mapped_column(String(30), default="text")  # text, select, number, textarea
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array for select
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    harga_tambahan: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    urutan: Mapped[int] = mapped_column(Integer, default=0)

    layanan: Mapped["Layanan"] = relationship("Layanan", back_populates="form_fields")

class Pesanan(Base):
    __tablename__ = "pesanan"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    layanan_id: Mapped[str] = mapped_column(ForeignKey("layanan.id"), index=True)
    varian_id: Mapped[str] = mapped_column(ForeignKey("layanan_varian.id"), index=True)
    kode: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="menunggu", index=True)
    alamat: Mapped[str] = mapped_column(Text)
    jadwal: Mapped[str] = mapped_column(String(50))  # ISO date string
    jam: Mapped[str] = mapped_column(String(10), default="")  # HH:MM
    durasi: Mapped[int] = mapped_column(Integer, default=1)  # jam/unit
    total_harga: Mapped[int] = mapped_column(Integer, default=0)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    komentar: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="pesanan")
    layanan: Mapped["Layanan"] = relationship("Layanan", back_populates="pesanan")
    varian: Mapped["LayananVarian"] = relationship("LayananVarian", back_populates="pesanan")
    notifikasi: Mapped[list["Notifikasi"]] = relationship("Notifikasi", back_populates="pesanan", cascade="all, delete-orphan")

class Notifikasi(Base):
    __tablename__ = "notifikasi"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    pesanan_id: Mapped[str | None] = mapped_column(ForeignKey("pesanan.id"), nullable=True, index=True)
    judul: Mapped[str] = mapped_column(String(200))
    pesan: Mapped[str] = mapped_column(Text)
    dibaca: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    pesanan: Mapped["Pesanan"] = relationship("Pesanan", back_populates="notifikasi")

# ── Production marketplace extensions ──

class ExternalIdentity(Base):
    __tablename__ = "external_identities"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    provider_subject: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Mitra(Base):
    __tablename__ = "mitra"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    nama: Mapped[str] = mapped_column(String(120))
    no_hp: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="tersedia", index=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MitraLayanan(Base):
    __tablename__ = "mitra_layanan"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mitra_id: Mapped[str] = mapped_column(ForeignKey("mitra.id"), index=True)
    layanan_id: Mapped[str] = mapped_column(ForeignKey("layanan.id"), index=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class PenugasanMitra(Base):
    __tablename__ = "penugasan_mitra"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    pesanan_id: Mapped[str] = mapped_column(ForeignKey("pesanan.id"), index=True)
    mitra_id: Mapped[str] = mapped_column(ForeignKey("mitra.id"), index=True)
    assigned_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ditugaskan", index=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    pesanan_id: Mapped[str] = mapped_column(ForeignKey("pesanan.id"), index=True)
    status_from: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status_to: Mapped[str] = mapped_column(String(30), index=True)
    changed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    pesanan_id: Mapped[str] = mapped_column(ForeignKey("pesanan.id"), index=True)
    method: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    amount: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
