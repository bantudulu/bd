import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_from_request
from app.database import get_db
from app.models import FormField, Layanan, LayananVarian, Pesanan

router = APIRouter(prefix="/api", tags=["api"])


class CreatePesananBody(BaseModel):
    layanan_id: str = Field(min_length=1, max_length=12)
    varian_id: str = Field(min_length=1, max_length=12)
    jadwal: str = Field(min_length=10, max_length=10)
    jam: str = Field(min_length=5, max_length=5)
    alamat: str = Field(min_length=5, max_length=1000)
    durasi: int = Field(default=1, ge=1, le=12)
    metode_pembayaran: Literal["cod", "transfer"] = "cod"
    catatan: str | None = Field(default=None, max_length=1000)
    form_data: dict[str, Any] = Field(default_factory=dict)

    # Kept only for backward compatibility with the current web client.
    # The server deliberately ignores this value and recalculates all add-ons.
    addon_total: int | None = Field(default=None, ge=0)

    @field_validator("layanan_id", "varian_id", "jadwal", "jam", "alamat")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field wajib tidak boleh kosong")
        return value

    @field_validator("catatan")
    @classmethod
    def strip_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("form_data")
    @classmethod
    def limit_form_data(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("Terlalu banyak field pada detail pesanan")
        return value


TRUTHY_VALUES = {True, 1, "1", "true", "on", "yes", "ya"}
FALSEY_VALUES = {False, 0, "0", "false", "off", "no", "tidak", "", None}
MAX_FORM_VALUE_LENGTH = 2000


def _parse_schedule(jadwal: str, jam: str) -> None:
    try:
        order_date = date.fromisoformat(jadwal)
    except ValueError as exc:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD") from exc

    today = datetime.now(timezone.utc).date()
    if order_date < today:
        raise HTTPException(400, "Tanggal pesanan tidak boleh di masa lalu")
    if order_date > today + timedelta(days=365):
        raise HTTPException(400, "Tanggal pesanan terlalu jauh")

    try:
        parsed_time = datetime.strptime(jam, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(400, "Format jam harus HH:MM") from exc

    # Current BantuDulu booking UI operates between 07:00 and 21:00.
    minutes = parsed_time.hour * 60 + parsed_time.minute
    if minutes < 7 * 60 or minutes > 21 * 60:
        raise HTTPException(400, "Jam layanan harus antara 07:00 dan 21:00")
    if parsed_time.minute not in {0, 30}:
        raise HTTPException(400, "Jam layanan harus menggunakan interval 30 menit")


def _field_key(field_id: str) -> str:
    return f"field_{field_id}"


def _is_checked(value: Any) -> bool:
    normalized = value.lower().strip() if isinstance(value, str) else value
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSEY_VALUES:
        return False
    raise HTTPException(400, "Nilai checkbox tidak valid")


def _load_options(raw_options: str | None) -> list[str]:
    if not raw_options:
        return []
    try:
        data = json.loads(raw_options)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(500, "Konfigurasi layanan tidak valid") from exc
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise HTTPException(500, "Konfigurasi opsi layanan tidak valid")
    return data


def _extract_option_price(selected_value: str, valid_options: list[str]) -> int:
    if selected_value not in valid_options:
        raise HTTPException(400, "Pilihan detail layanan tidak valid")

    parts = selected_value.split("|", 1)
    if len(parts) == 1 or not parts[1].strip():
        return 0

    try:
        extra = int(parts[1].strip())
    except ValueError as exc:
        raise HTTPException(500, "Konfigurasi harga tambahan layanan tidak valid") from exc
    if extra < 0:
        raise HTTPException(500, "Konfigurasi harga tambahan layanan tidak valid")
    return extra


def _validate_text_value(value: Any, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise HTTPException(400, "Detail layanan wajib belum diisi")
        return None
    text = str(value).strip()
    if required and not text:
        raise HTTPException(400, "Detail layanan wajib belum diisi")
    if len(text) > MAX_FORM_VALUE_LENGTH:
        raise HTTPException(400, "Isi detail layanan terlalu panjang")
    return text or None


def _calculate_form_price_and_validate(
    form_fields: list[FormField],
    submitted: dict[str, Any],
    durasi: int,
) -> tuple[int, dict[str, Any]]:
    known_keys = {_field_key(field.id) for field in form_fields}
    unknown_keys = set(submitted) - known_keys
    if unknown_keys:
        raise HTTPException(400, "Terdapat field detail layanan yang tidak dikenal")

    total_extra = 0
    sanitized: dict[str, Any] = {}

    for field in form_fields:
        key = _field_key(field.id)
        value = submitted.get(key)
        field_type = (field.field_type or "text").lower().strip()

        if field_type == "checkbox":
            checked = _is_checked(value) if key in submitted else False
            if field.required and not checked:
                raise HTTPException(400, f"{field.label} wajib dipilih")
            sanitized[key] = checked
            if checked:
                total_extra += max(0, int(field.harga_tambahan or 0))
            continue

        text = _validate_text_value(value, required=field.required)
        if text is None:
            continue

        if field_type == "select":
            options = _load_options(field.options)
            option_price = _extract_option_price(text, options)
            # Existing catalog encodes per-duration selectable work prices this way.
            total_extra += option_price * durasi
        elif field_type == "number":
            try:
                number_value = int(text)
            except ValueError as exc:
                raise HTTPException(400, f"{field.label} harus berupa angka") from exc
            if number_value < 0 or number_value > 100000:
                raise HTTPException(400, f"{field.label} di luar batas yang diizinkan")
            text = str(number_value)
        elif field_type not in {"text", "textarea"}:
            raise HTTPException(500, "Konfigurasi tipe field layanan tidak didukung")

        sanitized[key] = text

    # Preserve the existing catalog rule for Cuci Tandon Air, but derive it
    # from validated server-side form values rather than a client-supplied price.
    if any(isinstance(v, str) and "Lantai 2+" in v for v in sanitized.values()):
        total_extra += 50000

    return total_extra, sanitized


def _calculate_base_price(layanan: Layanan, varian: LayananVarian, durasi: int) -> int:
    tipe_hitung = (layanan.tipe_hitung or "per_jam").lower().strip()
    if tipe_hitung == "per_jam":
        return int(varian.harga) * durasi
    if tipe_hitung in {"per_unit", "per_pekerjaan", "per_order"}:
        return int(varian.harga)
    raise HTTPException(500, "Konfigurasi perhitungan layanan tidak valid")


async def _reject_probable_duplicate(
    db: AsyncSession,
    *,
    user_id: str,
    layanan_id: str,
    varian_id: str,
    jadwal: str,
    jam: str,
) -> None:
    # This protects the current web flow from accidental double-click/retry.
    # A DB-backed idempotency key will replace this guard in the migration phase.
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=20)
    result = await db.execute(
        select(Pesanan.id)
        .where(Pesanan.user_id == user_id)
        .where(Pesanan.layanan_id == layanan_id)
        .where(Pesanan.varian_id == varian_id)
        .where(Pesanan.jadwal == jadwal)
        .where(Pesanan.jam == jam)
        .where(Pesanan.created_at >= cutoff)
        .limit(1)
    )
    if result.scalar_one_or_none():
        raise HTTPException(409, "Pesanan yang sama baru saja dibuat. Silakan cek Pesanan Saya.")


@router.post("/pesanan")
async def create_pesanan(
    request: Request,
    data: CreatePesananBody,
    db: AsyncSession = Depends(get_db),
):
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Silakan login terlebih dahulu")
    if user.get("role") != "CUSTOMER":
        raise HTTPException(403, "Hanya customer yang dapat membuat pesanan")

    user_id = user.get("id")
    if not user_id:
        raise HTTPException(401, "Session tidak valid")

    _parse_schedule(data.jadwal, data.jam)

    layanan = await db.get(Layanan, data.layanan_id)
    if not layanan or not layanan.aktif:
        raise HTTPException(404, "Layanan tidak ditemukan atau sedang tidak aktif")

    varian = await db.get(LayananVarian, data.varian_id)
    if not varian:
        raise HTTPException(404, "Varian tidak ditemukan")
    if varian.layanan_id != layanan.id:
        raise HTTPException(400, "Varian tidak sesuai dengan layanan yang dipilih")
    if int(varian.harga) < 0:
        raise HTTPException(500, "Konfigurasi harga layanan tidak valid")

    fields_result = await db.execute(
        select(FormField)
        .where(FormField.layanan_id == layanan.id)
        .order_by(FormField.urutan)
    )
    form_fields = list(fields_result.scalars().all())

    extra_total, sanitized_form = _calculate_form_price_and_validate(
        form_fields,
        data.form_data,
        data.durasi,
    )
    base_total = _calculate_base_price(layanan, varian, data.durasi)
    total = base_total + extra_total

    if total < 0 or total > 100_000_000:
        raise HTTPException(400, "Total harga pesanan tidak valid")

    await _reject_probable_duplicate(
        db,
        user_id=user_id,
        layanan_id=layanan.id,
        varian_id=varian.id,
        jadwal=data.jadwal,
        jam=data.jam,
    )

    kode = f"BD-{uuid.uuid4().hex[:8].upper()}"
    simpan_form = {
        "metode_pembayaran": data.metode_pembayaran,
        **sanitized_form,
    }

    order = Pesanan(
        user_id=user_id,
        layanan_id=layanan.id,
        varian_id=varian.id,
        kode=kode,
        status="menunggu",
        alamat=data.alamat,
        jadwal=data.jadwal,
        jam=data.jam,
        durasi=data.durasi,
        total_harga=total,
        catatan=data.catatan,
        form_data=json.dumps(simpan_form, ensure_ascii=False),
    )

    db.add(order)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(order)

    return {
        "success": True,
        "data": {
            "id": order.id,
            "kode": order.kode,
            "status": order.status,
            "total_harga": order.total_harga,
        },
    }
