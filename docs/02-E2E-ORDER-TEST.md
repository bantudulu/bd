# 2. Full End-to-End Order Test

Jalankan dengan customer nyata internal dan mitra nyata yang sudah memberi izin.

## Skenario utama
Customer buat pesanan → Admin terima → Admin pilih mitra → Mitra konfirmasi → menuju lokasi → mulai pekerjaan → pekerjaan dilaporkan selesai → Admin verifikasi pekerjaan + COD → Admin set `selesai`.

## Skenario wajib
- Happy path sampai selesai.
- Customer batal sebelum pekerjaan berjalan.
- Admin batal dengan alasan.
- Tidak ada mitra untuk layanan.
- Mitra menolak lalu Admin mengganti mitra.
- Mitra tidak boleh mengambil order terbuka sendiri.
- Customer tidak melihat nama/no. WA mitra.
- Customer tidak melihat alasan internal pergantian mitra.
- Order legacy tetap tampil sebagai riwayat lama.
- Hanya Admin yang dapat menentukan status final `selesai`.
- COD harus diverifikasi Admin.
