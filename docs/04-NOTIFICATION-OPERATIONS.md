# 4. Notifikasi Operasional

Notifikasi in-app tetap menjadi sumber audit V1.

Admin dapat mengaudit record terbaru melalui:
`GET /api/ops/admin/notifications/recent?limit=50`

## V1
- Pesanan diterima.
- Tim menuju lokasi.
- Selesai.
- Dibatalkan.

WhatsApp otomatis belum boleh dianggap aktif sampai provider, kredensial, template, retry, dan delivery status benar-benar dikonfigurasi dan diuji.
