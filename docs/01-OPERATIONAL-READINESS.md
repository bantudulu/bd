# 1. Operational Readiness

Tujuan: memastikan BantuDulu siap menjalankan order nyata tanpa data palsu.

## Gate wajib
- Minimal 1 mitra nyata aktif.
- Setiap layanan yang ikut pilot memiliki minimal 1 mitra aktif.
- Nomor WA mitra valid.
- Tidak ada varian layanan aktif berharga Rp0.
- Tidak ada assignment aktif ganda.
- Order pada status yang memerlukan mitra harus mempunyai assignment aktif.
- Tidak membuat mitra/customer dummy di production.

## Alur Admin
1. Buka `/admin/mitra`.
2. Masukkan mitra nyata.
3. Hubungkan mitra ke layanan yang benar.
4. Buka `/admin/readiness`.
5. Pilot hanya dimulai ketika gate readiness hijau.\n\n## Koreksi legacy\nOrder sebelum Operational V1 (2026-09-07T06:29:07Z) adalah arsip dan tidak dihitung sebagai pekerjaan aktif. Varian bernama arsip dengan harga Rp0 tetap dipertahankan untuk histori dan tidak menjadi blocker readiness.\n