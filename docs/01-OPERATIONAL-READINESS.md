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
5. Pilot hanya dimulai ketika gate readiness hijau.
