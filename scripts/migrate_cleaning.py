"""
Migration: Restructure Bersih-Bersih → Cleaning
- Add catatan column to layanan table
- Rename kategori "Bersih-Bersih" → "Cleaning"
- Soft-delete old bersih layanan (aktif=0)
- Insert new layanan: Bersih Rumah + Cuci Tandon Air with varian & form_fields
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import async_session

def gen_id():
    return uuid.uuid4().hex[:12]

NEW_SERVICES = [
    {
        "nama": "Bersih Rumah",
        "deskripsi": "Layanan pembersihan rumah profesional dengan dua pilihan paket: Bersih Ringan untuk perawatan rutin harian, dan Bersih Berat untuk deep cleaning menyeluruh. Cocok untuk rumah, apartemen, kos, dan ruko.",
        "jenis_layanan": "bersih_rumah",
        "tipe_hitung": "per_jam",
        "catatan": "⏱️ Jika melebihi 1 jam, perhitungan berlaku kelipatan 30 menit.\n🚚 Ongkos kirim: 5 km gratis, lebihnya Rp10.000/km (berlaku kelipatan).",
        "varian": [
            {"nama": "Bersih Ringan", "harga": 60000, "deskripsi": "Pembersihan ringan rutin — sapu, pel, bersihkan debu"},
            {"nama": "Bersih Berat", "harga": 100000, "deskripsi": "Deep cleaning menyeluruh — kerak, noda membandel, area tersembunyi"},
        ],
        "form_fields": [
            {"label": "Jenis Tempat", "field_type": "select", "options": json.dumps(["Rumah", "Apartemen", "Kos", "Ruko"]), "required": True, "urutan": 1},
            {"label": "Jumlah Kamar", "field_type": "select", "options": json.dumps(["1 Kamar", "2 Kamar", "3 Kamar", "4+ Kamar"]), "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam", "2 Jam", "3 Jam", "4 Jam", "5+ Jam"]), "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "options": None, "required": False, "urutan": 4},
        ]
    },
    {
        "nama": "Cuci Tandon Air",
        "deskripsi": "Layanan cuci tandon air / tangki air bersih. Tandon yang kotor bisa menjadi sarang bakteri dan penyebab penyakit. Bersihkan tandon air Anda secara berkala untuk mendapatkan air bersih dan higienis. Melayani semua jenis tandon — plastik, stainless steel, hingga beton.",
        "jenis_layanan": "bersih_rumah",
        "tipe_hitung": "per_unit",
        "catatan": "🚚 Ongkos kirim: 5 km gratis, lebihnya Rp10.000/km (berlaku kelipatan).",
        "varian": [
            {"nama": "225–500 Liter", "harga": 100000, "deskripsi": "Tandon kapasitas 225–500 liter"},
            {"nama": "550–1.000 Liter", "harga": 150000, "deskripsi": "Tandon kapasitas 550–1.000 liter"},
            {"nama": "1.050–2.000 Liter", "harga": 200000, "deskripsi": "Tandon kapasitas 1.050–2.000 liter"},
            {"nama": "> 2.000 Liter", "harga": 250000, "deskripsi": "Tandon kapasitas di atas 2.000 liter"},
        ],
        "form_fields": [
            {"label": "Lokasi Tandon", "field_type": "select", "options": json.dumps(["Lantai 1 (mudah diakses)", "Lantai 2+ (butuh bantuan)", "Atas rumah / Rooftop"]), "required": True, "urutan": 1},
            {"label": "Jenis Tandon", "field_type": "select", "options": json.dumps(["Plastik / Tangki", "Stainless Steel", "Beton / Fiber"]), "required": True, "urutan": 2},
            {"label": "Catatan Tambahan", "field_type": "textarea", "options": None, "required": False, "urutan": 3},
        ]
    },
]


async def migrate():
    async with async_session() as db:
        # 1. Add catatan column if not exists
        try:
            await db.execute(text("ALTER TABLE layanan ADD COLUMN catatan TEXT"))
            print("✅ Column catatan added")
        except Exception as e:
            print(f"ℹ️  Column catatan may already exist: {e}")

        # 2. Rename kategori
        result = await db.execute(
            text("SELECT id FROM kategori WHERE slug = 'bersih' LIMIT 1")
        )
        row = result.fetchone()
        if not row:
            print("❌ Kategori bersih not found!")
            return

        kat_id = row[0]
        await db.execute(
            text("UPDATE kategori SET nama = 'Cleaning' WHERE id = :id"),
            {"id": kat_id}
        )
        print(f"✅ Kategori renamed to 'Cleaning' (id={kat_id})")

        # 3. Soft-delete old layanan
        result = await db.execute(
            text("SELECT id, nama FROM layanan WHERE kategori_id = :kid AND aktif = 1"),
            {"kid": kat_id}
        )
        old_layanan = result.fetchall()
        for l in old_layanan:
            await db.execute(
                text("UPDATE layanan SET aktif = 0 WHERE id = :id"),
                {"id": l[0]}
            )
            print(f"  → Soft-deleted: {l[1]} (id={l[0]})")

        # 4. Insert new layanan
        now = datetime.now(timezone.utc).isoformat()
        for svc in NEW_SERVICES:
            svc_id = gen_id()
            await db.execute(
                text("""
                    INSERT INTO layanan (id, kategori_id, nama, deskripsi, jenis_layanan, tipe_hitung, catatan, aktif, created_at)
                    VALUES (:id, :kid, :nama, :deskripsi, :jenis, :tipe, :catatan, 1, :now)
                """),
                {
                    "id": svc_id, "kid": kat_id,
                    "nama": svc["nama"], "deskripsi": svc["deskripsi"],
                    "jenis": svc["jenis_layanan"], "tipe": svc["tipe_hitung"],
                    "catatan": svc["catatan"],
                    "now": now,
                }
            )

            # Insert varian
            for v in svc["varian"]:
                v_id = gen_id()
                await db.execute(
                    text("""
                        INSERT INTO layanan_varian (id, layanan_id, nama, harga, deskripsi)
                        VALUES (:id, :lid, :nama, :harga, :deskripsi)
                    """),
                    {
                        "id": v_id, "lid": svc_id,
                        "nama": v["nama"], "harga": v["harga"],
                        "deskripsi": v["deskripsi"],
                    }
                )

            # Insert form fields
            for f in svc["form_fields"]:
                f_id = gen_id()
                options_val = f.get("options")
                await db.execute(
                    text("""
                        INSERT INTO form_fields (id, layanan_id, label, field_type, options, required, urutan)
                        VALUES (:id, :lid, :label, :ftype, :options, :required, :urutan)
                    """),
                    {
                        "id": f_id, "lid": svc_id,
                        "label": f["label"], "ftype": f["field_type"],
                        "options": options_val,
                        "required": 1 if f["required"] else 0,
                        "urutan": f["urutan"],
                    }
                )

            print(f"✅ Inserted: {svc['nama']} (id={svc_id})")

        await db.commit()
        print("\n🎉 Migration complete!")


asyncio.run(migrate())
