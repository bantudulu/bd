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


## Pricing scenarios before pilot
- Tukang Ringan: Rp70.000/jam, server ignores client price hints.
- Tukang Berat: Rp100.000/jam, server reads severity price from DB.
- Pijat: 5 km first free; confirmed excess km is rounded up and charged Rp10.000/km by Admin only.
- Reconfirming Pijat distance must be idempotent: old surcharge is replaced, not stacked.
- Paid order must reject distance-price changes.
- Cuci Tandon lantai 2 remains +Rp50.000.
- Bank/QRIS remain disabled for pilot; COD completion requires Admin confirmation.
