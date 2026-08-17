import asyncio, sqlite3, json, sys

# SQLite connection
sl = sqlite3.connect(r'C:\Users\SER5 MAX\bantudulu\app\bantudulu_v2.db')
sl.row_factory = sqlite3.Row

# Check tables in SQLite
tables = [r['name'] for r in sl.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("SQLite tables:", tables)

async def migrate():
    import aiomysql
    ma = await aiomysql.connect(
        host='127.0.0.1', port=3307,
        user='bantudulu_admin', password='bantuduluSQL',
        db='bantudulu_db', charset='utf8mb4'
    )
    
    async with ma.cursor() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS=0")
        
        # ── 1. users ──
        rows = sl.execute("SELECT * FROM users").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO users (id, nama, email, no_hp, password, role, foto, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['nama'], r['email'], r['no_hp'], r['password'], r['role'], r['foto'], r['created_at'], r['updated_at'])
            )
        print(f"✅ users: {len(rows)} rows")
        
        # ── 2. kategori ──
        rows = sl.execute("SELECT * FROM kategori").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO kategori (id, nama, icon, slug, warna, urutan, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['nama'], r['icon'], r['slug'], r['warna'], r['urutan'], r['created_at'])
            )
        print(f"✅ kategori: {len(rows)} rows")
        
        # ── 3. alamat ──
        rows = sl.execute("SELECT * FROM alamat").fetchall()
        for r in rows:
            try:
                await cur.execute(
                    "INSERT IGNORE INTO alamat (id, user_id, label, alamat_lengkap, lat, lng, is_default) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (r['id'], r['user_id'], r['label'], r['alamat_lengkap'], r['lat'], r['lng'], r['is_default'])
                )
            except Exception as e:
                print(f"  ⚠️ alamat {r['id']}: {e}")
        print(f"✅ alamat: {len(rows)} rows")
        
        # ── 4. layanan ──
        rows = sl.execute("SELECT * FROM layanan").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO layanan (id, kategori_id, nama, deskripsi, jenis_layanan, tipe_hitung, gambar_url, aktif, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['kategori_id'], r['nama'], r['deskripsi'], r['jenis_layanan'], r['tipe_hitung'], r['gambar_url'], r['aktif'], r['created_at'])
            )
        print(f"✅ layanan: {len(rows)} rows")
        
        # ── 5. layanan_varian ──
        rows = sl.execute("SELECT * FROM layanan_varian").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO layanan_varian (id, layanan_id, nama, harga, deskripsi) "
                "VALUES (%s, %s, %s, %s, %s)",
                (r['id'], r['layanan_id'], r['nama'], r['harga'], r['deskripsi'])
            )
        print(f"✅ layanan_varian: {len(rows)} rows")
        
        # ── 6. form_fields ──
        rows = sl.execute("SELECT * FROM form_fields").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO form_fields (id, layanan_id, label, field_type, options, required, urutan) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['layanan_id'], r['label'], r['field_type'], r['options'], r['required'], r['urutan'])
            )
        print(f"✅ form_fields: {len(rows)} rows")
        
        # ── 7. pesanan ──
        rows = sl.execute("SELECT * FROM pesanan").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO pesanan (id, user_id, layanan_id, varian_id, kode, status, alamat, jadwal, jam, durasi, total_harga, catatan, form_data, rating, komentar, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['user_id'], r['layanan_id'], r['varian_id'], r['kode'], r['status'], r['alamat'], r['jadwal'], r['jam'], r['durasi'], r['total_harga'], r['catatan'], r['form_data'], r['rating'], r['komentar'], r['created_at'], r['updated_at'])
            )
        print(f"✅ pesanan: {len(rows)} rows")
        
        # ── 8. notifikasi ──
        rows = sl.execute("SELECT * FROM notifikasi").fetchall()
        for r in rows:
            await cur.execute(
                "INSERT IGNORE INTO notifikasi (id, user_id, pesanan_id, judul, pesan, dibaca, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (r['id'], r['user_id'], r['pesanan_id'], r['judul'], r['pesan'], r['dibaca'], r['created_at'])
            )
        print(f"✅ notifikasi: {len(rows)} rows")
        
        await cur.execute("SET FOREIGN_KEY_CHECKS=1")
        await ma.commit()
        
        # Verify row counts
        await cur.execute("SELECT COUNT(*) FROM users"); u = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM kategori"); k = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM alamat"); a = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM layanan"); l = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM layanan_varian"); lv = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM form_fields"); ff = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM pesanan"); p = (await cur.fetchone())[0]
        await cur.execute("SELECT COUNT(*) FROM notifikasi"); n = (await cur.fetchone())[0]
        print(f"\n📊 Final counts:")
        print(f"  users={u} kategori={k} alamat={a} layanan={l} varian={lv} fields={ff} pesanan={p} notifikasi={n}")
    
    ma.close()
    sl.close()
    print("\n✅ Migration complete!")

asyncio.run(migrate())
