"""
Migration: Rename Pijat & Relaksasi → Trapis
- Add harga_tambahan column to form_fields table
- Soft-delete old pijat layanan (aktif=0)
- Insert new Trapis layanan with addon checkboxes
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import async_session

def gen_id():
    return uuid.uuid4().hex[:12]

NEW_SERVICE = {
    "nama": "Trapis",
    "deskripsi": "Layanan pijat tradisional Trapis — relaksasi tubuh dengan sentuhan khas Makassar. Tersedia sesi 60 menit dengan tambahan paket Refleksi, Kretek, atau Kerokan sesuai kebutuhan Anda. Terapis profesional dan sopan.",
    "jenis_layanan": "pijat_relaksasi",
    "tipe_hitung": "per_jam",
    "catatan": "🚚 Ongkos kirim: 5 km gratis, lebihnya Rp10.000/km (berlaku kelipatan).",
    "varian": [
        {"nama": "60 Menit", "harga": 100000, "deskripsi": "Sesi pijat Trapis 60 menit"},
    ],
    "form_fields": [
        {"label": "Pilih Pemijat", "field_type": "select", "options": json.dumps(["Pria", "Wanita"]), "required": True, "urutan": 1},
        {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam (60 Menit)", "2 Jam (120 Menit)"]), "required": True, "urutan": 2},
        {"label": "Alamat Lengkap", "field_type": "textarea", "required": True, "urutan": 3},
        {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        {"label": "+ Refleksi", "field_type": "checkbox", "options": None, "required": False, "urutan": 5, "harga_tambahan": 30000},
        {"label": "+ Kretek", "field_type": "checkbox", "options": None, "required": False, "urutan": 6, "harga_tambahan": 30000},
        {"label": "+ Kerokan", "field_type": "checkbox", "options": None, "required": False, "urutan": 7, "harga_tambahan": 20000},
    ]
}

async def migrate():
    async with async_session() as db:
        # 1. Add harga_tambahan column if not exists
        try:
            await db.execute(text("ALTER TABLE form_fields ADD COLUMN harga_tambahan INTEGER"))
            print("✅ Column harga_tambahan added")
        except Exception as e:
            print(f"ℹ️  Column harga_tambahan may already exist: {e}")

        # 2. Find pijat kategori
        result = await db.execute(
            text("SELECT id FROM kategori WHERE slug = 'pijat' LIMIT 1")
        )
        row = result.fetchone()
        if not row:
            print("❌ Kategori pijat not found!")
            return
        kat_id = row[0]
        print(f"✅ Found kategori pijat (id={kat_id})")

        # 3. Soft-delete old pijat layanan
        result = await db.execute(
            text("SELECT id, nama FROM layanan WHERE kategori_id = :kid AND aktif = 1"),
            {"kid": kat_id}
        )
        old = result.fetchall()
        for l in old:
            await db.execute(
                text("UPDATE layanan SET aktif = 0 WHERE id = :id"),
                {"id": l[0]}
            )
            print(f"  → Soft-deleted: {l[1]} (id={l[0]})")

        # 4. Insert new Trapis
        now = datetime.now(timezone.utc).isoformat()
        svc = NEW_SERVICE
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
                text("INSERT INTO layanan_varian (id, layanan_id, nama, harga, deskripsi) VALUES (:id, :lid, :nama, :harga, :deskripsi)"),
                {"id": v_id, "lid": svc_id, "nama": v["nama"], "harga": v["harga"], "deskripsi": v["deskripsi"]}
            )

        # Insert form fields with harga_tambahan
        for f in svc["form_fields"]:
            f_id = gen_id()
            ht = f.get("harga_tambahan")
            await db.execute(
                text("""
                    INSERT INTO form_fields (id, layanan_id, label, field_type, options, required, harga_tambahan, urutan)
                    VALUES (:id, :lid, :label, :ftype, :options, :required, :ht, :urutan)
                """),
                {
                    "id": f_id, "lid": svc_id,
                    "label": f["label"], "ftype": f["field_type"],
                    "options": f.get("options"),
                    "required": 1 if f["required"] else 0,
                    "ht": ht,
                    "urutan": f["urutan"],
                }
            )

        await db.commit()
        print(f"\n✅ Inserted: {svc['nama']} (id={svc_id})")
        print("🎉 Migration complete!")

asyncio.run(migrate())
