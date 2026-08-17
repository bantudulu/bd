"""
Migrasi: AC & Elektronik → Jasa Antar
- Ganti nama kategori + slug + icon
- Ganti nama layanan + tipe_hitung
- Hapus varian lama (Cuci AC Standar, Bongkar Pasang, dll) → Mobil, Motor
- Hapus form fields lama → Alamat Jemput, Alamat Antar, Catatan
"""
import asyncio, sys
sys.path.insert(0, '.')

from app.database import async_session
from app.models import Kategori, Layanan, LayananVarian, FormField
from sqlalchemy import select, delete

async def migrate():
    async with async_session() as db:
        # 1. Cari kategori lama
        r = await db.execute(select(Kategori).where(Kategori.slug == 'elektronik'))
        kat = r.scalar_one_or_none()
        if not kat:
            print("❌ Kategori 'elektronik' not found!")
            return
        print(f"✅ Found kategori: {kat.nama} (id={kat.id})")

        # 2. Update kategori
        kat.nama = "Jasa Antar"
        kat.slug = "antar"
        kat.icon = "🚚"
        kat.warna = "#f97316"  # orange
        print(f"✅ Kategori renamed to: {kat.nama}")

        # 3. Cari layanan Cuci AC
        r2 = await db.execute(select(Layanan).where(
            Layanan.kategori_id == kat.id
        ))
        lay = r2.scalar_one_or_none()
        if not lay:
            print("❌ Layanan not found!")
            return
        print(f"✅ Found layanan: {lay.nama} (id={lay.id})")

        # 4. Update layanan
        lay.nama = "Jasa Antar"
        lay.deskripsi = "Layanan antar jemput barang, paket, dokumen, dan lainnya menggunakan kendaraan roda dua atau roda empat. Cepat, aman, dan terpercaya."
        lay.jenis_layanan = "antar"
        lay.tipe_hitung = "per_jam"
        lay.catatan = "🚚 Ongkos kirim sudah termasuk dalam harga.\\n⏱️ Durasi antar berlaku kelipatan 30 menit."
        print(f"✅ Layanan renamed to: {lay.nama}")

        # 5. Hapus varian lama
        await db.execute(delete(LayananVarian).where(
            LayananVarian.layanan_id == lay.id
        ))
        print("✅ Old variants deleted")

        # 6. Tambah varian baru
        varian_baru = [
            {"nama": "Mobil", "harga": 100000, "deskripsi": "Antar pakai mobil — muat hingga 4 barang besar"},
            {"nama": "Motor", "harga": 50000, "deskripsi": "Antar pakai motor — cepat untuk dokumen & paket kecil"},
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
            {"label": "Alamat Jemput", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Alamat Antar", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": '["1 Jam", "2 Jam", "3 Jam", "4 Jam"]', "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
        for f in fields_baru:
            db.add(FormField(layanan_id=lay.id, **f))
        print(f"✅ {len(fields_baru)} new form fields added")

        # 9. Commit
        await db.commit()
        print("\n✅✅✅ Migrasi Jasa Antar berhasil!")

asyncio.run(migrate())
