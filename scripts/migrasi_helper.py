"""
Migrasi: Bantu Belanja → Helper
- Ganti nama kategori + slug + icon
- Ganti nama layanan + deskripsi
- Hapus varian lama → 1 varian: 60 Menit Rp100.000
- Hapus form fields lama → Alamat, Catatan, Durasi
"""
import asyncio, sys
sys.path.insert(0, '.')

from app.database import async_session
from app.models import Kategori, Layanan, LayananVarian, FormField
from sqlalchemy import select, delete

async def migrate():
    async with async_session() as db:
        # 1. Cari kategori lama
        r = await db.execute(select(Kategori).where(Kategori.slug == 'belanja'))
        kat = r.scalar_one_or_none()
        if not kat:
            print("❌ Kategori 'belanja' not found!")
            return
        print(f"✅ Found kategori: {kat.nama} (id={kat.id})")

        # 2. Update kategori
        kat.nama = "Helper"
        kat.slug = "helper"
        kat.icon = "🦺"
        kat.warna = "#f59e0b"
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
        lay.nama = "Helper"
        lay.deskripsi = "Jasa bantu-bantu — angkat barang, pindahan, belanja, antar dokumen, atau bantuan apa pun yang kamu butuhkan. Cocok untuk yang lagi sibuk atau butuh tenaga tambahan."
        lay.jenis_layanan = "helper"
        lay.tipe_hitung = "per_jam"
        lay.catatan = "⏱️ Durasi berlaku kelipatan 30 menit.\\n📦 Barang berat / jumlah banyak akan dikenakan biaya tambahan."
        print(f"✅ Layanan renamed to: {lay.nama}")

        # 5. Hapus varian lama
        await db.execute(delete(LayananVarian).where(
            LayananVarian.layanan_id == lay.id
        ))
        print("✅ Old variants deleted")

        # 6. Tambah varian baru
        db.add(LayananVarian(
            layanan_id=lay.id,
            nama="60 Menit",
            harga=100000,
            deskripsi="Sesi helper 60 menit — angkat barang, belanja, atau bantuan lainnya"
        ))
        print("✅ New variant added")

        # 7. Hapus form fields lama
        await db.execute(delete(FormField).where(
            FormField.layanan_id == lay.id
        ))
        print("✅ Old form fields deleted")

        # 8. Tambah form fields baru
        fields_baru = [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Deskripsi Pekerjaan", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": '["1 Jam", "2 Jam", "3 Jam", "4 Jam"]', "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
        for f in fields_baru:
            db.add(FormField(layanan_id=lay.id, **f))
        print(f"✅ {len(fields_baru)} new form fields added")

        # 9. Commit
        await db.commit()
        print("\n✅✅✅ Migrasi Helper berhasil!")

asyncio.run(migrate())
