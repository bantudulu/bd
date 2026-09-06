from sqlalchemy import select
from app.database import async_session
from app.models import FormField, Kategori, Layanan, LayananVarian

async def ensure_final_catalog():
    async with async_session() as db:
        kat=(await db.execute(select(Kategori).where(Kategori.slug=="pijat"))).scalar_one_or_none()
        if not kat: return
        services=(await db.execute(select(Layanan).where(Layanan.kategori_id==kat.id))).scalars().all()
        svc=next((s for s in services if s.jenis_layanan=="pijat_relaksasi"),None)
        if not svc: return
        if svc.nama=="Trapis": svc.nama="Pijat & Relaksasi"
        variants=(await db.execute(select(LayananVarian).where(LayananVarian.layanan_id==svc.id))).scalars().all()
        existing={v.nama.casefold():v for v in variants}
        for name,price,desc in [("Pijat Biasa",100000,"Pijatan umum untuk membantu tubuh lebih rileks."),("Pijat Full Body",120000,"Pijatan menyeluruh untuk seluruh bagian tubuh.")]:
            if name.casefold() not in existing: db.add(LayananVarian(layanan_id=svc.id,nama=name,harga=price,deskripsi=desc))
        fields=(await db.execute(select(FormField).where(FormField.layanan_id==svc.id))).scalars().all()
        if not any("pijat muka" in f.label.casefold() for f in fields): db.add(FormField(layanan_id=svc.id,label="+ Pijat Muka",field_type="checkbox",harga_tambahan=30000,required=False,urutan=8))
        await db.commit()
