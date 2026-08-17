import asyncio
import os
os.environ['DB_ENGINE'] = 'mysql'

import sys
sys.path.insert(0, r'C:\Users\SER5 MAX\bantudulu')

from app.database import async_session
from app.models import Layanan, Kategori, LayananVarian, Pesanan, User, Notifikasi
from sqlalchemy import select, func

async def check():
    async with async_session() as db:
        # 1. Check layanan references
        result = await db.execute(select(Layanan))
        layanans = result.scalars().all()
        print(f"Total layanan: {len(layanans)}")
        for l in layanans:
            r = await db.execute(select(Kategori).where(Kategori.id == l.kategori_id))
            k = r.scalar_one_or_none()
            if not k:
                print(f"  [FAIL] Layanan '{l.nama}' -> kategori_id {l.kategori_id} NOT FOUND!")
            else:
                print(f"  [OK] {l.nama} -> kategori '{k.nama}'")
            
            vr = await db.execute(select(LayananVarian).where(LayananVarian.layanan_id == l.id))
            vc = len(vr.scalars().all())
            if vc == 0:
                print(f"  [WARN] {l.nama}: 0 varian!")
            else:
                print(f"  [OK] {l.nama}: {vc} varian")
        
        # 2. Check pesanan references
        pr = await db.execute(select(Pesanan))
        pesanans = pr.scalars().all()
        print(f"\nTotal pesanan: {len(pesanans)}")
        zero_price = 0
        for p in pesanans:
            lr = await db.execute(select(Layanan).where(Layanan.id == p.layanan_id))
            l = lr.scalar_one_or_none()
            vr = await db.execute(select(LayananVarian).where(LayananVarian.id == p.varian_id))
            v = vr.scalar_one_or_none()
            if not l:
                print(f"  [FAIL] Pesanan {p.kode}: layanan NOT FOUND")
            if not v:
                print(f"  [FAIL] Pesanan {p.kode}: varian NOT FOUND")
            if p.total_harga <= 0:
                zero_price += 1
                if zero_price <= 3:
                    print(f"  [WARN] Pesanan {p.kode}: harga Rp{p.total_harga}")
        
        if zero_price > 0:
            print(f"  [WARN] Total pesanan dengan harga Rp0: {zero_price}")
        
        # 3. Check user stats
        ur = await db.execute(select(User))
        users = ur.scalars().all()
        admin_count = sum(1 for u in users if u.role == 'ADMIN')
        customer_count = sum(1 for u in users if u.role == 'CUSTOMER')
        print(f"\nUsers: {len(users)} total ({admin_count} admin, {customer_count} customer)")
        for u in users:
            print(f"  {u.role:10s} | {u.email:30s} | {u.nama:20s} | {u.no_hp}")

        # 4. Pesanan by status
        for status in ['menunggu', 'diproses', 'ditugaskan', 'selesai', 'dibatalkan']:
            sr = await db.execute(select(func.count(Pesanan.id)).where(Pesanan.status == status))
            count = sr.scalar()
            if count > 0:
                print(f"  Pesanan status '{status}': {count}")

    print("\n=== AUDIT COMPLETE ===")

asyncio.run(check())
