# BantuDulu Production Readiness

Dokumen ini adalah runbook minimum sebelum BantuDulu menerima traffic production.

## 1. Environment freeze

Wajib:

- `APP_ENV=production`
- `ENABLE_DEV_SEED=false`
- `SECRET_KEY` random minimal 32 karakter dan disimpan di secret/env server, bukan Git
- database MySQL/MariaDB melalui `DATABASE_URL=mysql+aiomysql://...` atau field `MYSQL_*`
- SQLite tidak boleh digunakan di production

Jangan pernah menaruh `.env`, dump database, token, password, atau credential provider ke repository.

## 2. Deployment order

Urutan deployment wajib:

1. Backup database sebelum perubahan schema/deploy.
2. Pull/checkout commit release yang sudah lolos CI.
3. Sinkronkan dependency dari `uv.lock`.
4. Jalankan `python -m scripts.migrate` menggunakan environment production.
5. Pastikan migration selesai pada schema version terbaru.
6. Restart web service.
7. Cek `/health/live` harus HTTP 200.
8. Cek `/health/ready` harus HTTP 200 dan status `ready`.
9. Lakukan smoke journey: login customer, lihat layanan, buat satu order test terkontrol, assign petugas dari admin, ubah status sesuai lifecycle, verifikasi notifikasi customer.
10. Hapus/batalkan data smoke test jika memang dibuat pada production.

Web process production tidak menjalankan migration otomatis. Bila database belum pada versi schema yang diwajibkan, startup diblokir.

## 3. Migration discipline

`schema_migrations` menyimpan versi schema yang sudah diterapkan. Baseline hardened schema adalah version 1.

Setiap perubahan schema berikutnya harus:

- menaikkan `LATEST_SCHEMA_VERSION`;
- memiliki langkah migration version baru yang eksplisit;
- diuji pada database kosong dan database dari versi sebelumnya;
- tidak bergantung pada web startup untuk mengubah schema.

## 4. Health checks

- `GET /health/live`: memastikan process aplikasi hidup; tidak bergantung pada database.
- `GET /health/ready`: memastikan database dapat diakses dan, pada production, schema sudah current.

Load balancer/reverse proxy hanya boleh mengirim traffic ke instance yang `ready`.

## 5. Backup & restore

Sebelum setiap release yang menyentuh schema, buat dump MySQL/MariaDB dengan tool resmi server (`mysqldump`/`mariadb-dump`) dan simpan terenkripsi di lokasi terpisah dari VPS aplikasi.

Minimum operasional:

- backup harian database;
- retention minimal 7 backup harian dan 4 backup mingguan;
- lakukan restore rehearsal ke database terpisah secara berkala;
- backup dianggap valid hanya setelah pernah berhasil direstore dan aplikasi dapat membaca data hasil restore.

Jangan restore langsung menimpa production sebelum membuat snapshot/dump kondisi terakhir.

## 6. Rollback release

Jika release baru bermasalah tetapi schema masih backward-compatible:

1. hentikan traffic ke release bermasalah;
2. checkout commit aplikasi terakhir yang sehat;
3. restart service;
4. cek health endpoints;
5. lakukan smoke test.

Jika migration bersifat tidak backward-compatible, rollback harus mengikuti prosedur migration khusus versi tersebut atau restore database dari backup. Jangan menjalankan downgrade improvisasi pada production.

## 7. Logging & incident basics

Log production tidak boleh mencetak password, access token, refresh token, cookie auth, secret key, database password, atau push token penuh. Pertahankan log service/reverse proxy dengan rotasi dan retention yang masuk akal untuk investigasi insiden.

Untuk incident kritis: hentikan perubahan baru, catat waktu mulai, release SHA, gejala, dampak customer, tindakan yang diambil, lalu lakukan post-incident review setelah layanan stabil.

## 8. GO / NO-GO gate

GO hanya bila seluruh poin berikut terpenuhi:

- CI branch/release hijau;
- migration rehearsal sukses;
- backup dan restore rehearsal sukses;
- secret production sudah fresh dan tidak pernah tersimpan di Git;
- tidak ada akun demo/default pada database production;
- `/health/live` dan `/health/ready` hijau;
- full customer-to-admin order journey sukses di staging/rehearsal;
- domain/TLS/reverse proxy final sudah aktif;
- owner/operator tahu prosedur backup, rollback, dan incident response.

Jika salah satu blocker di atas belum selesai, statusnya NO-GO untuk public production traffic.
