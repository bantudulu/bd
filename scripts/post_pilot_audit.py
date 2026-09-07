from __future__ import annotations
import asyncio
from sqlalchemy import and_, func, select
from app.database import async_session
from app.models import Layanan, LayananVarian, Mitra, PaymentTransaction, PenugasanMitra, Pesanan

REQUIRES_ASSIGNMENT={"ditugaskan","menuju_lokasi","dimulai","menunggu_konfirmasi"}

async def main():
    async with async_session() as db:
        status_rows=(await db.execute(select(Pesanan.status,func.count(Pesanan.id)).group_by(Pesanan.status).order_by(Pesanan.status))).all()
        missing=(await db.execute(
            select(func.count(Pesanan.id))
            .outerjoin(PenugasanMitra,and_(PenugasanMitra.pesanan_id==Pesanan.id,PenugasanMitra.aktif==True))
            .where(Pesanan.status.in_(tuple(REQUIRES_ASSIGNMENT)),PenugasanMitra.id.is_(None))
        )).scalar_one()
        dup=(await db.execute(
            select(func.count()).select_from(
                select(PenugasanMitra.pesanan_id).where(PenugasanMitra.aktif==True)
                .group_by(PenugasanMitra.pesanan_id).having(func.count(PenugasanMitra.id)>1).subquery()
            )
        )).scalar_one()
        inactive=(await db.execute(
            select(func.count(PenugasanMitra.id)).join(Mitra,Mitra.id==PenugasanMitra.mitra_id)
            .where(PenugasanMitra.aktif==True,Mitra.aktif==False)
        )).scalar_one()
        bad_price=(await db.execute(select(func.count(Pesanan.id)).where(Pesanan.total_harga<=0))).scalar_one()
        non_cod=(await db.execute(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.method!="cod"))).scalar_one()
        zero_variant=(await db.execute(
            select(func.count(LayananVarian.id)).join(Layanan,Layanan.id==LayananVarian.layanan_id)
            .where(Layanan.aktif==True,LayananVarian.harga<=0)
        )).scalar_one()
        print("=== BANTUDULU POST-PILOT AUDIT (READ-ONLY) ===")
        for s,c in status_rows: print(f"status.{s}: {c}")
        print("missing_required_assignment:",missing)
        print("duplicate_active_assignment:",dup)
        print("inactive_partner_active_assignment:",inactive)
        print("order_total_le_zero:",bad_price)
        print("non_cod_payment_transactions:",non_cod)
        print("active_service_zero_price_variant:",zero_variant)
        blockers=int(missing or 0)+int(dup or 0)+int(inactive or 0)+int(bad_price or 0)+int(zero_variant or 0)
        if blockers:
            print("AUDIT RESULT: BLOCKED"); raise SystemExit(2)
        print("AUDIT RESULT: PASS (database integrity checks)")

if __name__=="__main__":
    asyncio.run(main())
