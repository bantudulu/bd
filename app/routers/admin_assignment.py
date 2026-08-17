from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Assignment, Layanan, LayananVarian, Notifikasi, Pesanan, Petugas, User

router = APIRouter(prefix="/api/admin", tags=["admin-assignment"])


def require_admin(request: Request) -> dict:
    user = request.state.user
    if not user or user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya admin.")
    return user


class PetugasCreate(BaseModel):
    nama: str = Field(min_length=2, max_length=100)
    no_hp: str = Field(min_length=8, max_length=20)
    foto: str | None = Field(default=None, max_length=255)
    keahlian: str | None = Field(default=None, max_length=2000)
    wilayah: str | None = Field(default=None, max_length=150)
    catatan_internal: str | None = Field(default=None, max_length=3000)


class PetugasUpdate(BaseModel):
    nama: str | None = Field(default=None, min_length=2, max_length=100)
    no_hp: str | None = Field(default=None, min_length=8, max_length=20)
    foto: str | None = Field(default=None, max_length=255)
    keahlian: str | None = Field(default=None, max_length=2000)
    wilayah: str | None = Field(default=None, max_length=150)
    aktif: bool | None = None
    catatan_internal: str | None = Field(default=None, max_length=3000)


class AssignmentCreate(BaseModel):
    petugas_id: str = Field(min_length=1, max_length=12)
    alasan_penggantian: str | None = Field(default=None, max_length=1000)


class OperationalStatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=30)


STATUS_TRANSITIONS = {
    "menunggu": {"dibatalkan"},
    "diproses": {"dibatalkan"},  # legacy state only
    "ditugaskan": {"menuju_lokasi", "dibatalkan"},
    "menuju_lokasi": {"dimulai", "dibatalkan"},
    "dimulai": {"selesai"},
    "selesai": set(),
    "dibatalkan": set(),
}


def petugas_payload(p: Petugas) -> dict:
    return {
        "id": p.id,
        "nama": p.nama,
        "no_hp": p.no_hp,
        "foto": p.foto,
        "keahlian": p.keahlian,
        "wilayah": p.wilayah,
        "aktif": p.aktif,
        "catatan_internal": p.catatan_internal,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


async def _find_order(db: AsyncSession, identifier: str) -> Pesanan | None:
    result = await db.execute(
        select(Pesanan).where((Pesanan.id == identifier) | (Pesanan.kode == identifier))
    )
    return result.scalar_one_or_none()


@router.get("/petugas")
async def list_petugas(
    request: Request,
    aktif: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    require_admin(request)
    stmt = select(Petugas).order_by(Petugas.nama.asc())
    if aktif is not None:
        stmt = stmt.where(Petugas.aktif == aktif)
    result = await db.execute(stmt)
    return [petugas_payload(p) for p in result.scalars().all()]


@router.post("/petugas", status_code=201)
async def create_petugas(
    body: PetugasCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    require_admin(request)
    petugas = Petugas(**body.model_dump())
    db.add(petugas)
    await db.commit()
    await db.refresh(petugas)
    return petugas_payload(petugas)


@router.put("/petugas/{petugas_id}")
async def update_petugas(
    petugas_id: str,
    body: PetugasUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    require_admin(request)
    petugas = await db.get(Petugas, petugas_id)
    if not petugas:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan.")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(petugas, key, value)

    await db.commit()
    await db.refresh(petugas)
    return petugas_payload(petugas)


@router.get("/operasional/pesanan")
async def list_operational_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Operational queue used by the admin assignment dashboard."""
    require_admin(request)
    active_statuses = {"menunggu", "diproses", "ditugaskan", "menuju_lokasi", "dimulai"}
    result = await db.execute(
        select(Pesanan)
        .where(Pesanan.status.in_(active_statuses))
        .order_by(Pesanan.created_at.asc())
    )
    orders = result.scalars().all()

    payload = []
    for order in orders:
        customer = await db.get(User, order.user_id)
        layanan = await db.get(Layanan, order.layanan_id)
        varian = await db.get(LayananVarian, order.varian_id)

        assignment_result = await db.execute(
            select(Assignment)
            .where(Assignment.pesanan_id == order.id, Assignment.status == "aktif")
            .order_by(Assignment.assigned_at.desc())
            .limit(1)
        )
        active_assignment = assignment_result.scalar_one_or_none()
        active_worker = await db.get(Petugas, active_assignment.petugas_id) if active_assignment else None

        count_result = await db.execute(
            select(func.count(Assignment.id)).where(Assignment.pesanan_id == order.id)
        )
        assignment_count = int(count_result.scalar() or 0)

        payload.append({
            "id": order.id,
            "kode": order.kode,
            "status": order.status,
            "jadwal": order.jadwal,
            "jam": order.jam,
            "durasi": order.durasi,
            "alamat": order.alamat,
            "catatan": order.catatan,
            "total_harga": order.total_harga,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "pelanggan": {
                "nama": customer.nama if customer else "Unknown",
                "no_hp": customer.no_hp if customer else None,
            },
            "layanan": {
                "nama": layanan.nama if layanan else "Layanan",
                "jenis_layanan": layanan.jenis_layanan if layanan else None,
                "varian": varian.nama if varian else None,
            },
            "assignment": {
                "id": active_assignment.id,
                "assigned_at": active_assignment.assigned_at.isoformat() if active_assignment.assigned_at else None,
                "petugas": {
                    "id": active_worker.id,
                    "nama": active_worker.nama,
                    "no_hp": active_worker.no_hp,
                    "wilayah": active_worker.wilayah,
                    "keahlian": active_worker.keahlian,
                } if active_worker else None,
            } if active_assignment else None,
            "assignment_count": assignment_count,
            "needs_worker": active_assignment is None,
        })

    return payload


@router.put("/operasional/pesanan/{pesanan_id}/status")
async def update_operational_status(
    pesanan_id: str,
    body: OperationalStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    require_admin(request)
    order = await _find_order(db, pesanan_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan.")

    target = body.status.lower().strip()
    current = (order.status or "").lower().strip()
    allowed = STATUS_TRANSITIONS.get(current)
    if allowed is None or target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Perubahan status {current} -> {target} tidak diizinkan.",
        )

    if target in {"menuju_lokasi", "dimulai", "selesai"}:
        assignment_result = await db.execute(
            select(Assignment.id).where(
                Assignment.pesanan_id == order.id,
                Assignment.status == "aktif",
            )
        )
        if assignment_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=409, detail="Pesanan belum memiliki petugas aktif.")

    order.status = target
    await db.commit()
    await db.refresh(order)
    return {"success": True, "id": order.id, "kode": order.kode, "status": order.status}


@router.get("/pesanan/{pesanan_id}/assignment")
async def get_assignment_history(
    pesanan_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    require_admin(request)
    order = await _find_order(db, pesanan_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan.")

    result = await db.execute(
        select(Assignment)
        .where(Assignment.pesanan_id == order.id)
        .order_by(Assignment.assigned_at.desc())
    )
    assignments = result.scalars().all()

    data = []
    for assignment in assignments:
        petugas = await db.get(Petugas, assignment.petugas_id)
        admin = await db.get(User, assignment.assigned_by)
        data.append({
            "id": assignment.id,
            "status": assignment.status,
            "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            "replaced_at": assignment.replaced_at.isoformat() if assignment.replaced_at else None,
            "replaced_reason": assignment.replaced_reason,
            "assigned_by": admin.nama if admin else None,
            "petugas": {
                "id": petugas.id,
                "nama": petugas.nama,
                "foto": petugas.foto,
                "wilayah": petugas.wilayah,
                "no_hp": petugas.no_hp,
            } if petugas else None,
        })

    return {"pesanan_id": order.id, "kode": order.kode, "assignments": data}


@router.post("/pesanan/{pesanan_id}/assign")
async def assign_petugas(
    pesanan_id: str,
    body: AssignmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    admin = require_admin(request)
    order = await _find_order(db, pesanan_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan.")
    if order.status in {"selesai", "dibatalkan"}:
        raise HTTPException(status_code=409, detail="Pesanan yang sudah selesai/dibatalkan tidak dapat ditugaskan.")

    petugas = await db.get(Petugas, body.petugas_id)
    if not petugas or not petugas.aktif:
        raise HTTPException(status_code=400, detail="Petugas tidak tersedia atau tidak aktif.")

    current_result = await db.execute(
        select(Assignment).where(
            Assignment.pesanan_id == order.id,
            Assignment.status == "aktif",
        )
    )
    current = current_result.scalar_one_or_none()

    if current and current.petugas_id == petugas.id:
        raise HTTPException(status_code=409, detail="Petugas tersebut sudah aktif pada pesanan ini.")
    if current and not body.alasan_penggantian:
        raise HTTPException(status_code=400, detail="Alasan penggantian wajib diisi saat mengganti petugas.")

    now = datetime.now(timezone.utc)
    try:
        if current:
            current.status = "diganti"
            current.replaced_at = now
            current.replaced_reason = body.alasan_penggantian

        assignment = Assignment(
            pesanan_id=order.id,
            petugas_id=petugas.id,
            assigned_by=admin.get("id"),
            status="aktif",
            assigned_at=now,
        )
        db.add(assignment)
        order.status = "ditugaskan"

        notification_title = "Petugas BantuDulu sudah siap"
        if current:
            notification_message = (
                f"Petugas untuk pesanan {order.kode} telah diperbarui. "
                f"{petugas.nama} akan membantu pesanan Anda."
            )
        else:
            notification_message = f"{petugas.nama} telah ditugaskan untuk membantu pesanan {order.kode}."

        db.add(Notifikasi(
            user_id=order.user_id,
            pesanan_id=order.id,
            judul=notification_title,
            pesan=notification_message,
        ))

        await db.commit()
        await db.refresh(assignment)
    except Exception:
        await db.rollback()
        raise

    return {
        "success": True,
        "pesanan": {"id": order.id, "kode": order.kode, "status": order.status},
        "assignment": {
            "id": assignment.id,
            "petugas_id": petugas.id,
            "petugas_nama": petugas.nama,
            "assigned_at": assignment.assigned_at.isoformat(),
            "status": assignment.status,
        },
        "reassigned": current is not None,
    }
