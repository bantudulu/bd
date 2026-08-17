from app.database import async_session
from app.models import Kategori, Layanan, LayananVarian, User, FormField
from app.auth import hash_password
from sqlalchemy import select
import json

KATEGORI_DEFAULT = [
    {"nama": "Cleaning", "icon": "🧹", "slug": "bersih", "warna": "#14b8a6", "urutan": 1},
    {"nama": "Jasa Antar", "icon": "🚚", "slug": "antar", "warna": "#f97316", "urutan": 2},
    {"nama": "Tukang", "icon": "🔧", "slug": "tukang", "warna": "#6b7280", "urutan": 3},
    {"nama": "Pijat & Relaksasi", "icon": "💆", "slug": "pijat", "warna": "#ec4899", "urutan": 4},
    {"nama": "MUA", "icon": "💄", "slug": "mua", "warna": "#db2777", "urutan": 5},
    {"nama": "Helper", "icon": "🦺", "slug": "helper", "warna": "#f59e0b", "urutan": 6},
    {"nama": "Dekor", "icon": "🎉", "slug": "dekor", "warna": "#f43f5e", "urutan": 7},
    {"nama": "Web Desain", "icon": "🌐", "slug": "web-desain", "warna": "#6366f1", "urutan": 8},
]

LAYANAN_DEFAULT = [
    {
        "kategori_slug": "bersih",
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
            {"label": "Jenis Tempat", "field_type": "select", "options": json.dumps(["Rumah", "Apartemen", "Kos", "Ruko"]), "urutan": 1},
            {"label": "Jumlah Kamar", "field_type": "select", "options": json.dumps(["1 Kamar", "2 Kamar", "3 Kamar", "4+ Kamar"]), "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam", "2 Jam", "3 Jam", "4 Jam", "5+ Jam"]), "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "bersih",
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
            {"label": "Lokasi Tandon", "field_type": "select", "options": json.dumps(["Lantai 1 (mudah diakses)", "Lantai 2+ (butuh bantuan)"]), "urutan": 1},
            {"label": "Jenis Tandon", "field_type": "select", "options": json.dumps(["Plastik / Tangki", "Stainless Steel", "Beton / Fiber"]), "urutan": 2},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 3},
        ]
    },
    {
        "kategori_slug": "antar",
        "nama": "Jasa Antar",
        "deskripsi": "Layanan antar jemput barang, paket, dokumen, dan lainnya menggunakan kendaraan roda dua atau roda empat. Cepat, aman, dan terpercaya.",
        "jenis_layanan": "antar",
        "tipe_hitung": "per_jam",
        "catatan": "🚚 Ongkos kirim sudah termasuk dalam harga.\\n⏱️ Durasi antar berlaku kelipatan 30 menit.",
        "varian": [
            {"nama": "Mobil", "harga": 100000, "deskripsi": "Antar pakai mobil — muat hingga 4 barang besar"},
            {"nama": "Motor", "harga": 50000, "deskripsi": "Antar pakai motor — cepat untuk dokumen & paket kecil"},
        ],
        "form_fields": [
            {"label": "Alamat Jemput", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Alamat Antar", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam", "2 Jam", "3 Jam", "4 Jam"]), "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "tukang",
        "nama": "Tukang",
        "deskripsi": "Tukang serba bisa untuk perbaikan rumah — listrik, pipa, dan lainnya. Dapatkan bantuan teknisi berpengalaman untuk memperbaiki, memasang, atau merawat instalasi di rumah Anda.",
        "jenis_layanan": "tukang",
        "tipe_hitung": "per_jam",
        "catatan": "⏱️ Durasi berlaku kelipatan 30 menit.\\n🔧 Hanya jasa tukang, material/onderdil tidak termasuk.",
        "varian": [
            {"nama": "Kelistrikan", "harga": 70000, "deskripsi": "Perbaikan & instalasi listrik — stop kontak, saklar, lampu, panel"},
            {"nama": "Perpipaan", "harga": 70000, "deskripsi": "Perbaikan & instalasi pipa — kran bocor, saluran mampet, toilet"},
        ],
        "form_fields": [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Deskripsi Masalah", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam", "2 Jam", "3 Jam", "4 Jam"]), "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "pijat",
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
            {"label": "+ Refleksi", "field_type": "checkbox", "harga_tambahan": 30000, "required": False, "urutan": 5},
            {"label": "+ Kretek", "field_type": "checkbox", "harga_tambahan": 30000, "required": False, "urutan": 6},
            {"label": "+ Kerokan", "field_type": "checkbox", "harga_tambahan": 20000, "required": False, "urutan": 7},
        ]
    },
    {
        "kategori_slug": "mua",
        "nama": "Makeup Reguler",
        "deskripsi": "Makeup untuk acara reguler — pesta, wisuda, bridesmaid, lamaran, siraman, hingga prewedding. Hasil natural hingga glam sesuai kebutuhan.",
        "jenis_layanan": "mua",
        "tipe_hitung": "per_pekerjaan",
        "varian": [
            {"nama": "Party, pendamping wisuda, photo shoot", "harga": 200000, "deskripsi": "Makeup untuk pesta, pendamping wisuda, atau photo shoot kasual"},
            {"nama": "Wisuda-bridesmaid", "harga": 300000, "deskripsi": "Makeup untuk wisuda atau sebagai pendamping pengantin (bridesmaid)"},
            {"nama": "Lamaran, Siraman, Preweding", "harga": 400000, "deskripsi": "Makeup untuk acara lamaran, siraman, atau sesi prewedding"},
        ],
        "form_fields": [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Jam Mulai", "field_type": "text", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan (gaya makeup, jenis kulit, dll)", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "mua",
        "nama": "Makeup Wedding",
        "deskripsi": "Makeup pengantin profesional untuk hari bahagia Anda. Dari Mappaci, akad nikah, hingga resepsi — lengkap dengan riasan orang tua.",
        "jenis_layanan": "mua",
        "tipe_hitung": "per_pekerjaan",
        "varian": [
            {"nama": "Mappaci, akad, resepsi", "harga": 1200000, "deskripsi": "Paket lengkap Mappaci, akad nikah, dan resepsi — 3 sesi makeup"},
            {"nama": "Akad dan Resepsi", "harga": 2000000, "deskripsi": "Makeup untuk akad nikah dan resepsi — 2 sesi, hasil eksklusif"},
            {"nama": "Akad Nikah + Ortu", "harga": 1300000, "deskripsi": "Makeup akad nikah untuk pengantin + riasan untuk orang tua"},
        ],
        "form_fields": [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Jam Mulai", "field_type": "text", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan (gaya makeup, jenis kulit, dll)", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "helper",
        "nama": "Helper",
        "deskripsi": "Jasa bantu-bantu — angkat barang, pindahan, belanja, antar dokumen, atau bantuan apa pun yang kamu butuhkan. Cocok untuk yang lagi sibuk atau butuh tenaga tambahan.",
        "jenis_layanan": "helper",
        "tipe_hitung": "per_jam",
        "catatan": "⏱️ Durasi berlaku kelipatan 30 menit.\\n📦 Barang berat / jumlah banyak akan dikenakan biaya tambahan.",
        "varian": [
            {"nama": "Ringan", "harga": 70000, "deskripsi": "Pekerjaan ringan — angkat barang kecil, belanja, antar dokumen, bantuan ringan lainnya"},
            {"nama": "Berat", "harga": 100000, "deskripsi": "Pekerjaan berat — pindahan, angkat barang besar, bongkar muat, bantuan berat lainnya"},
        ],
        "form_fields": [
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 1},
            {"label": "Deskripsi Pekerjaan", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Durasi", "field_type": "select", "options": json.dumps(["1 Jam", "2 Jam", "3 Jam", "4 Jam"]), "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    # ── Dekor ──
    {
        "kategori_slug": "dekor",
        "nama": "Dekorasi Aqiqah",
        "deskripsi": "Dekorasi aqiqah yang indah dan khidmat untuk menyambut buah hati Anda. Tersedia berbagai pilihan tema dan konsep sesuai keinginan.",
        "jenis_layanan": "dekorasi",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🎯 Konsultasi tema dan warna sebelum hari H.\\n🚚 Biaya transportasi menyesuaikan lokasi.",
        "varian": [
            {"nama": "Standar", "harga": 700000, "deskripsi": "Paket dekorasi aqiqah standar"},
        ],
        "form_fields": [
            {"label": "Tema", "field_type": "text", "required": True, "urutan": 1},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "dekor",
        "nama": "Dekorasi Mappatuada",
        "deskripsi": "Dekorasi untuk acara Mappatuada (tradisi adat Bugis-Makassar). Konsep adat yang autentik dan elegan.",
        "jenis_layanan": "dekorasi",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🎯 Konsultasi tema dan konsep adat sebelum hari H.\\n🚚 Biaya transportasi menyesuaikan lokasi.",
        "varian": [
            {"nama": "Standar", "harga": 650000, "deskripsi": "Paket dekorasi Mappatuada"},
        ],
        "form_fields": [
            {"label": "Tema Adat", "field_type": "text", "required": True, "urutan": 1},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "dekor",
        "nama": "Dekorasi Ulang Tahun",
        "deskripsi": "Dekorasi ulang tahun dengan tema favorit Anda. Mulai dari dekorasi sederhana hingga mewah.",
        "jenis_layanan": "dekorasi",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🎯 Konsultasi tema sebelum hari H.\\n🎈 Harga tergantung kompleksitas.",
        "varian": [
            {"nama": "Standar", "harga": 500000, "deskripsi": "Balon, backdrop sederhana"},
            {"nama": "Premium", "harga": 700000, "deskripsi": "Backdrop tema, balon, hiasan meja"},
        ],
        "form_fields": [
            {"label": "Tema", "field_type": "text", "required": True, "urutan": 1},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "dekor",
        "nama": "Paket Ulang Tahun",
        "deskripsi": "Paket lengkap pesta ulang tahun anak! Dekorasi + MC Badut + Sulap + Balon. Hemat dan praktis — all-in-one.",
        "jenis_layanan": "dekorasi",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🎈 Max. 50 orang anak.\\n🎯 Konsultasi tema setelah pemesanan.\\n⏱️ Durasi 2-3 jam.",
        "varian": [
            {"nama": "Paket Lengkap", "harga": 1100000, "deskripsi": "Dekorasi + MC Badut + Sulap + Balon (Max. 50 anak)"},
        ],
        "form_fields": [
            {"label": "Tema Ulang Tahun", "field_type": "text", "required": True, "urutan": 1},
            {"label": "Jumlah Anak", "field_type": "text", "required": True, "urutan": 2},
            {"label": "Tanggal Acara", "field_type": "text", "required": True, "urutan": 3},
            {"label": "Jam Mulai", "field_type": "text", "required": True, "urutan": 4},
            {"label": "Alamat", "field_type": "textarea", "required": True, "urutan": 5},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 6},
        ]
    },
    # ── Web Desain ──
    {
        "kategori_slug": "web-desain",
        "nama": "Website Biasa",
        "deskripsi": "Website personal / landing page sederhana. Cocok untuk profil usaha, portofolio, atau blog pribadi. (Domain & hosting tidak termasuk).",
        "jenis_layanan": "web_desain",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🌐 Domain dan hosting tidak termasuk dalam harga.\\n📄 Desain maksimal 5 halaman.\\n🔧 Revisi maksimal 2×.",
        "varian": [
            {"nama": "Standar", "harga": 500000, "deskripsi": "Website biasa — landing page / profil (max 5 halaman)"},
        ],
        "form_fields": [
            {"label": "Jenis Website", "field_type": "select", "options": json.dumps(["Landing Page", "Profil Usaha", "Portfolio", "Blog Sederhana"]), "required": True, "urutan": 1},
            {"label": "Deskripsi Kebutuhan", "field_type": "textarea", "required": True, "urutan": 2},
            {"label": "Deadline", "field_type": "text", "required": True, "urutan": 3},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 4},
        ]
    },
    {
        "kategori_slug": "web-desain",
        "nama": "Website Company",
        "deskripsi": "Website perusahaan profesional — multi-halaman, profil perusahaan, layanan, kontak, galeri. Cocok untuk bisnis resmi yang butuh tampilan profesional. (Domain & hosting tidak termasuk).",
        "jenis_layanan": "web_desain",
        "tipe_hitung": "per_pekerjaan",
        "catatan": "🌐 Domain dan hosting tidak termasuk dalam harga.\\n📄 Harga mulai dari Rp1.000.000, tergantung kompleksitas.\\n🔧 Revisi maksimal 3×.",
        "varian": [
            {"nama": "Mulai", "harga": 1000000, "deskripsi": "Website company — multi-halaman, profil, layanan, kontak, galeri"},
        ],
        "form_fields": [
            {"label": "Jumlah Halaman", "field_type": "select", "options": json.dumps(["5–10 Halaman", "10–20 Halaman", "20+ Halaman"]), "required": True, "urutan": 1},
            {"label": "Fitur Tambahan", "field_type": "select", "options": json.dumps(["Tidak Ada", "Galeri Foto", "Form Kontak", "Blog/Artikel", "Multi Bahasa"]), "required": True, "urutan": 2},
            {"label": "Deskripsi Kebutuhan", "field_type": "textarea", "required": True, "urutan": 3},
            {"label": "Deadline", "field_type": "text", "required": True, "urutan": 4},
            {"label": "Catatan Tambahan", "field_type": "textarea", "required": False, "urutan": 5},
        ]
    },
]

ADMIN_DEFAULT = {
    "nama": "Admin BantuDulu",
    "email": "admin@bantudulu.id",
    "no_hp": "081388889282",
    "password": "admin123",
    "role": "ADMIN",
}

CUSTOMER_DEFAULT = {
    "nama": "Demo User",
    "email": "user@bantudulu.id",
    "no_hp": "081388889283",
    "password": "user1234",
    "role": "CUSTOMER",
}

async def seed_data():
    async with async_session() as db:
        # Cek apakah sudah ada data
        result = await db.execute(select(Kategori).limit(1))
        if result.scalar_one_or_none():
            return  # Already seeded

        # Seed admin
        admin_exists = await db.execute(select(User).where(User.email == ADMIN_DEFAULT["email"]))
        if not admin_exists.scalar_one_or_none():
            db.add(User(
                nama=ADMIN_DEFAULT["nama"],
                email=ADMIN_DEFAULT["email"],
                no_hp=ADMIN_DEFAULT["no_hp"],
                password=hash_password(ADMIN_DEFAULT["password"]),
                role=ADMIN_DEFAULT["role"],
            ))

        # Seed customer
        cust_exists = await db.execute(select(User).where(User.email == CUSTOMER_DEFAULT["email"]))
        if not cust_exists.scalar_one_or_none():
            db.add(User(
                nama=CUSTOMER_DEFAULT["nama"],
                email=CUSTOMER_DEFAULT["email"],
                no_hp=CUSTOMER_DEFAULT["no_hp"],
                password=hash_password(CUSTOMER_DEFAULT["password"]),
                role=CUSTOMER_DEFAULT["role"],
            ))

        # Seed kategori + layanan
        for k_data in KATEGORI_DEFAULT:
            kategori = Kategori(**k_data)
            db.add(kategori)
            await db.flush()

            for l_data_orig in LAYANAN_DEFAULT:
                if l_data_orig["kategori_slug"] != k_data["slug"]:
                    continue

                # Copy to avoid mutating the original
                l_data = l_data_orig.copy()
                varian_list = l_data.pop("varian")
                form_fields_list = l_data.pop("form_fields")
                l_data.pop("kategori_slug")

                layanan = Layanan(kategori_id=kategori.id, **l_data)
                db.add(layanan)
                await db.flush()

                for v in varian_list:
                    db.add(LayananVarian(layanan_id=layanan.id, **v))

                for f in form_fields_list:
                    db.add(FormField(layanan_id=layanan.id, **f))

        await db.commit()
