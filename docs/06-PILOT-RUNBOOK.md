# 6. Pilot BantuDulu

Target awal: 3–5 customer nyata, mitra nyata, sekitar 1 minggu, seluruh order diawasi Admin.

- Mulai hanya jika `/admin/readiness` tidak memiliki blocker.
- Jangan mengejar volume.
- Semua order harus dapat ditelusuri dari dibuat sampai terminal.
- Admin mencatat kejadian tak normal pada hari yang sama.
- Tidak boleh memalsukan order atau performa pilot.


## Go / No-Go
Pilot hanya boleh mulai bila seluruh kondisi berikut terpenuhi:
- `/admin/readiness` mengembalikan `ready_for_pilot=true`.
- Setiap layanan yang dibuka untuk pilot memiliki minimal satu mitra nyata yang memang kompeten pada layanan tersebut.
- Minimal satu Real E2E post-Operational-V1 berhasil sampai status `selesai`.
- Harga Tukang Ringan/Berat dan ongkos jarak Pijat sudah diuji pada order nyata internal.
- COD adalah metode pembayaran pilot; Bank/QRIS tetap nonaktif.
- Customer, mitra, atau hasil pilot tidak boleh dibuat-buat untuk sekadar membuat readiness hijau.
