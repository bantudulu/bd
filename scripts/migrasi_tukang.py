"""
Migrasi: Les Privat → Tukang
- Ganti nama kategori + slug + icon
- Ganti nama layanan + deskripsi
- Hapus varian lama → Kelistrikan, Perpipaan @ Rp70.000/jam
- Hapus form fields lama → Alamat, Deskripsi, Durasi, Catatan
"""
import asyncio, sys
sys.path.insert(0, '.')

from app.database import async_session
from app.models import Kategori, Layanan, LayananVarian, FormField
from sqlalchemy import select, delete

async def migrate():
    async with async_session() as db:
        # 1. Cari kategori lama
        r = await db.execute(select(Kategori).where(Kategori.slug == 'les'))
        kat = r.scalar_one_or_none()
        if not kat:
            print("❌ Kategori 'les' not found!")
            return
        print(f"✅ Found kategori: {kat.nama} (id={kat.id})")

        # 2. Update kategori
        kat.nama = "Tukang"
        kat.slug = "tukang"
        kat.icon = "🔧"
        kat.warna = "#6b7280"
        print(f"✅ Kategori renamed to: {kat.nama}")

        # 3. Cari layanan
        r2 = await db.execute(select(Layanan).where(
            Layanan.kategori_id == kat.id
        ))
        lay = r2.scalar_one_or_none()
        if not lay:
            print("❌ Layanan not found!")
            return
        print(f"✅ Found layanan: {lay.nama} (id={lay.id})")

        # 4. Update layanan
        lay.nama = "Tukang"
        lay.deskripsi = "Tukang serba bisa untuk perbaikan rumah — listrik, pipa, dan lainnya. Dapatkan bantuan teknisi berpengalaman untuk memperbaiki, memasang, atau merawat instalasi di rumah Anda."
        lay.jenis_layanan = "tukang"
        lay.tipe_hitung = "per_jam"
        lay.catatan = "⏱️ Durasi berlaku kelipatan 30 menit.\\n🔧 Hanya jasa tukang, material/onderdil tidak termasuk."
        print(f"✅ Layanan renamed to: {lay.nama}")

        # 5. Hapus varian lama
        await db.execute(delete(LayananVarian).where(
            LayananVarian.layanan_id == lay.id
        ))
        print("✅ Old variants deleted")

        # 6. Tambah varian baru
        varian_baru = [
            {"nama": "Kelistrikan", "harga": 70000, "deskripsi": "Perbaikan & instalasi listrik — stop kontak, saklar, lampu, panel"},
            {"nama": "Perpipaan", "harga": 70000, "deskripsi": "Perbaikan & instalasi pipa — kran bocor, saluran mampet, toilet"},
        ]
        for v in varian_baru:
            db.add(LayananVarian(layanan_id=lay.id, **v))
        print(f"✅ {len(varian_baru)} new variants added")

        # 7. Hapus form fields lama
        await db.execute(delete(FormField).where(
            FormField.layanan_id == lay.id
        ))
        print("✅ Old form fields deleted")

        # 8. Tambah form fields baru
        fields_baru = [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Deskripsi Masalah", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": '["1 Jam", "2 Jam", "3 Jam", "4 Jam"]', "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
        for f in fields_baru:
            db.add(FormField(layanan_id=lay.id, **f))
        print(f"✅ {len(fields_baru)} new form fields added")

        # 9. Commit
        await db.commit()
        print("\n✅✅✅ Migrasi Tukang berhasil!")

asyncio.run(migrate())
