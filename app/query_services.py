from collections import defaultdict
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Kategori, Layanan, LayananVarian, Pesanan, Petugas, User


async def service_min_prices(db: AsyncSession, service_ids: Iterable[str]) -> dict[str, int]:
    ids = [value for value in dict.fromkeys(service_ids) if value]
    if not ids:
        return {}
    result = await db.execute(
        select(LayananVarian.layanan_id, func.min(LayananVarian.harga))
        .where(LayananVarian.layanan_id.in_(ids))
        .group_by(LayananVarian.layanan_id)
    )
    return {service_id: int(price or 0) for service_id, price in result.all()}


async def catalog_maps(db: AsyncSession, services: Iterable[Layanan]) -> tuple[dict, dict]:
    rows = list(services)
    category_ids = [row.kategori_id for row in rows if row.kategori_id]
    category_map: dict[str, Kategori] = {}
    if category_ids:
        result = await db.execute(select(Kategori).where(Kategori.id.in_(set(category_ids))))
        category_map = {row.id: row for row in result.scalars().all()}
    prices = await service_min_prices(db, [row.id for row in rows])
    return category_map, prices


async def order_related_maps(db: AsyncSession, orders: Iterable[Pesanan]) -> dict[str, dict]:
    rows = list(orders)
    if not rows:
        return {"services": {}, "variants": {}, "users": {}, "assignments": {}, "workers": {}}

    service_ids = {row.layanan_id for row in rows if row.layanan_id}
    variant_ids = {row.varian_id for row in rows if row.varian_id}
    user_ids = {row.user_id for row in rows if row.user_id}
    order_ids = {row.id for row in rows}

    services = {}
    variants = {}
    users = {}
    if service_ids:
        result = await db.execute(select(Layanan).where(Layanan.id.in_(service_ids)))
        services = {row.id: row for row in result.scalars().all()}
    if variant_ids:
        result = await db.execute(select(LayananVarian).where(LayananVarian.id.in_(variant_ids)))
        variants = {row.id: row for row in result.scalars().all()}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = {row.id: row for row in result.scalars().all()}

    assignments: dict[str, Assignment] = {}
    workers = {}
    if order_ids:
        result = await db.execute(
            select(Assignment)
            .where(Assignment.pesanan_id.in_(order_ids), Assignment.status == "aktif")
            .order_by(Assignment.assigned_at.desc())
        )
        for assignment in result.scalars().all():
            assignments.setdefault(assignment.pesanan_id, assignment)
        worker_ids = {row.petugas_id for row in assignments.values() if row.petugas_id}
        if worker_ids:
            worker_result = await db.execute(select(Petugas).where(Petugas.id.in_(worker_ids)))
            workers = {row.id: row for row in worker_result.scalars().all()}

    return {
        "services": services,
        "variants": variants,
        "users": users,
        "assignments": assignments,
        "workers": workers,
    }


async def variants_by_service(db: AsyncSession, service_ids: Iterable[str]) -> dict[str, list[LayananVarian]]:
    ids = [value for value in dict.fromkeys(service_ids) if value]
    grouped: dict[str, list[LayananVarian]] = defaultdict(list)
    if not ids:
        return grouped
    result = await db.execute(
        select(LayananVarian)
        .where(LayananVarian.layanan_id.in_(ids))
        .order_by(LayananVarian.layanan_id, LayananVarian.harga.asc())
    )
    for row in result.scalars().all():
        grouped[row.layanan_id].append(row)
    return grouped
