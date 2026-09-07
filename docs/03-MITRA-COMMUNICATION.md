# 3. Komunikasi Mitra V1

V1 memakai model managed service, bukan marketplace terbuka.

- Admin yang memilih mitra.
- Mitra tidak melihat pool order.
- Admin boleh menghubungi mitra melalui WhatsApp.
- Data kontak mitra tidak pernah diberikan ke customer.
- Respons mitra dicatat melalui aksi operasional BantuDulu.

Backend menyediakan endpoint Admin-only:
`GET /api/ops/admin/orders/{order_id}/contact`

Endpoint mengembalikan deep-link WhatsApp untuk customer dan mitra yang sedang ditugaskan.
