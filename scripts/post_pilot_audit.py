from __future__ import annotations

import asyncio
import os

DATABASE_URL_RAW=os.getenv("DATABASE_URL","").strip()
VALID_POSTGRES_PREFIXES=("postgres://","postgresql://","postgresql+asyncpg://")
if not DATABASE_URL_RAW or not DATABASE_URL_RAW.startswith(VALID_POSTGRES_PREFIXES):
    print("AUDIT ABORTED: DATABASE_URL PostgreSQL production tidak tersedia/valid. SQLite fallback tidak diizinkan untuk audit production.")
    raise SystemExit(3)

from sqlalchemy import and_, func, select
from app.database import async_session
from app.models import Layanan,LayananVarian,Mitra,PaymentTransaction,PenugasanMitra,Pesanan
from app.operational_policy import OPERATIONAL_V1_CUTOFF_DB

REQUIRES_ASSIGNMENT={"ditugaskan","menuju_lokasi","dimulai","menunggu_konfirmasi"}
ACTIVE={"menunggu","diproses","ditugaskan","menuju_lokasi","dimulai","menunggu_konfirmasi"}

def current_order_conditions():
    return (
        Pesanan.created_at>=OPERATIONAL_V1_CUTOFF_DB,
        func.length(func.trim(func.coalesce(Pesanan.alamat,"")))>0,
        func.length(func.trim(func.coalesce(Pesanan.jadwal,"")))>0,
        func.length(func.trim(func.coalesce(Pesanan.jam,"")))>0,
    )

async def main():
    async with async_session() as db:
        status_rows=(await db.execute(select(Pesanan.status,func.count(Pesanan.id)).group_by(Pesanan.status).order_by(Pesanan.status))).all()
        legacy_archive=(await db.execute(select(func.count(Pesanan.id)).where(Pesanan.created_at<OPERATIONAL_V1_CUTOFF_DB))).scalar_one()
        current_active=(await db.execute(select(func.count(Pesanan.id)).where(Pesanan.status.in_(tuple(ACTIVE)),*current_order_conditions()))).scalar_one()
        missing=(await db.execute(
            select(func.count(Pesanan.id)).outerjoin(PenugasanMitra,and_(PenugasanMitra.pesanan_id==Pesanan.id,PenugasanMitra.aktif==True))
            .where(Pesanan.status.in_(tuple(REQUIRES_ASSIGNMENT)),*current_order_conditions(),PenugasanMitra.id.is_(None))
        )).scalar_one()
        dup=(await db.execute(
            select(func.count()).select_from(
                select(PenugasanMitra.pesanan_id).join(Pesanan,Pesanan.id==PenugasanMitra.pesanan_id)
                .where(PenugasanMitra.aktif==True,*current_order_conditions())
                .group_by(PenugasanMitra.pesanan_id).having(func.count(PenugasanMitra.id)>1).subquery()
            )
        )).scalar_one()
        inactive=(await db.execute(
            select(func.count(PenugasanMitra.id)).join(Mitra,Mitra.id==PenugasanMitra.mitra_id).join(Pesanan,Pesanan.id==PenugasanMitra.pesanan_id)
            .where(PenugasanMitra.aktif==True,Mitra.aktif==False,*current_order_conditions())
        )).scalar_one()
        bad_price=(await db.execute(select(func.count(Pesanan.id)).where(Pesanan.total_harga<=0,*current_order_conditions()))).scalar_one()
        non_cod=(await db.execute(
            select(func.count(PaymentTransaction.id)).join(Pesanan,Pesanan.id==PaymentTransaction.pesanan_id)
            .where(PaymentTransaction.method!="cod",*current_order_conditions())
        )).scalar_one()
        zero_variant=(await db.execute(
            select(func.count(LayananVarian.id)).join(Layanan,Layanan.id==LayananVarian.layanan_id)
            .where(Layanan.aktif==True,LayananVarian.harga<=0,~func.lower(func.coalesce(LayananVarian.nama,"")).like("%arsip%"))
        )).scalar_one()
        archived_zero_variant=(await db.execute(
            select(func.count(LayananVarian.id)).join(Layanan,Layanan.id==LayananVarian.layanan_id)
            .where(Layanan.aktif==True,LayananVarian.harga<=0,func.lower(func.coalesce(LayananVarian.nama,"")).like("%arsip%"))
        )).scalar_one()

        print("=== BANTUDULU POST-PILOT AUDIT (READ-ONLY) ===")
        print("operational_v1_cutoff:",OPERATIONAL_V1_CUTOFF_DB.isoformat()+"Z")
        for s,c in status_rows: print(f"status.{s}: {c}")
        print("legacy_archive_orders:",legacy_archive)
        print("current_active_orders:",current_active)
        print("missing_required_assignment_current:",missing)
        print("duplicate_active_assignment_current:",dup)
        print("inactive_partner_active_assignment_current:",inactive)
        print("current_order_total_le_zero:",bad_price)
        print("current_non_cod_payment_transactions:",non_cod)
        print("operational_zero_price_variant:",zero_variant)
        print("archived_zero_price_variant_ignored:",archived_zero_variant)

        blockers=int(missing or 0)+int(dup or 0)+int(inactive or 0)+int(bad_price or 0)+int(non_cod or 0)+int(zero_variant or 0)
        if blockers:
            print("AUDIT RESULT: BLOCKED")
            raise SystemExit(2)
        print("AUDIT RESULT: PASS (current Operational V1 integrity checks)")

if __name__=="__main__":
    asyncio.run(main())
