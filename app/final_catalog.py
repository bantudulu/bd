from sqlalchemy import select

from app.database import async_session
from app.models import FormField, Kategori, Layanan, LayananVarian


async def _category(db, slug, nama, icon, warna, urutan):
    item = (await db.execute(select(Kategori).where(Kategori.slug == slug))).scalar_one_or_none()
    if item:
        return item
    item = Kategori(nama=nama, icon=icon, slug=slug, warna=warna, urutan=urutan)
    db.add(item)
    await db.flush()
    return item


async def _service(db, kategori, nama, jenis_layanan, tipe_hitung, deskripsi, catatan=None):
    item = (
        await db.execute(
            select(Layanan).where(
                Layanan.kategori_id == kategori.id,
                Layanan.nama == nama,
            )
        )
    ).scalar_one_or_none()
    if item:
        return item
    item = Layanan(
        kategori_id=kategori.id,
        nama=nama,
        deskripsi=deskripsi,
        jenis_layanan=jenis_layanan,
        tipe_hitung=tipe_hitung,
        catatan=catatan,
        aktif=True,
    )
    db.add(item)
    await db.flush()
    return item


async def _variant(db, layanan, nama, harga, deskripsi):
    existing = (
        await db.execute(
            select(LayananVarian).where(
                LayananVarian.layanan_id == layanan.id,
                LayananVarian.nama == nama,
            )
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(LayananVarian(layanan_id=layanan.id, nama=nama, harga=harga, deskripsi=deskripsi))


async def ensure_final_catalog():
    async with async_session() as db:
        tukang_cat = await _category(db, "tukang", "Tukang", "🔧", "#6b7280", 3)
        tukang = await _service(
            db,
            tukang_cat,
            "Tukang",
            "tukang",
            "per_jam",
            "Tukang serba bisa untuk perbaikan rumah, kelistrikan, dan perpipaan.",
            "Harga adalah jasa. Material atau onderdil tidak termasuk.",
        )
        await _variant(db, tukang, "Kelistrikan", 70000, "Perbaikan dan instalasi listrik rumah.")
        await _variant(db, tukang, "Perpipaan", 70000, "Perbaikan dan instalasi pipa, kran, dan saluran.")

        web_cat = await _category(db, "web-desain", "Web Desain", "🌐", "#6366f1", 8)
        web_basic = await _service(
            db,
            web_cat,
            "Website Biasa",
            "web_desain",
            "per_pekerjaan",
            "Website personal atau landing page sederhana untuk profil usaha dan portofolio.",
            "Domain dan hosting tidak termasuk dalam harga.",
        )
        await _variant(db, web_basic, "Standar", 500000, "Website biasa atau landing page, maksimal 5 halaman.")

        web_company = await _service(
            db,
            web_cat,
            "Website Company",
            "web_desain",
            "per_pekerjaan",
            "Website perusahaan profesional dengan beberapa halaman dan fitur bisnis.",
            "Domain dan hosting tidak termasuk dalam harga.",
        )
        await _variant(db, web_company, "Mulai", 1000000, "Website company multi-halaman.")

        pijat_cat = (await db.execute(select(Kategori).where(Kategori.slug == "pijat"))).scalar_one_or_none()
        if pijat_cat:
            services = (await db.execute(select(Layanan).where(Layanan.kategori_id == pijat_cat.id))).scalars().all()
            svc = next((s for s in services if s.jenis_layanan == "pijat_relaksasi"), None)
            if svc:
                if svc.nama == "Trapis":
                    svc.nama = "Pijat & Relaksasi"
                await _variant(db, svc, "Pijat Biasa", 100000, "Pijatan umum untuk membantu tubuh lebih rileks.")
                await _variant(db, svc, "Pijat Full Body", 120000, "Pijatan menyeluruh untuk seluruh bagian tubuh.")
                fields = (await db.execute(select(FormField).where(FormField.layanan_id == svc.id))).scalars().all()
                if not any("pijat muka" in f.label.casefold() for f in fields):
                    db.add(FormField(layanan_id=svc.id,label="+ Pijat Muka",field_type="checkbox",harga_tambahan=30000,required=False,urutan=8))

        await db.commit()
