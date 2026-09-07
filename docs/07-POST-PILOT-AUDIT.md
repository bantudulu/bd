# 7. Audit Setelah Pilot

Jalankan `python scripts/post_pilot_audit.py` pada environment yang mempunyai akses database production.

Audit read-only:
- distribusi status order,
- order aktif tanpa assignment ketika assignment diwajibkan,
- assignment aktif ganda,
- assignment aktif ke mitra nonaktif,
- COD/payment consistency,
- harga order <= 0,
- varian aktif Rp0.

Launch ditahan jika ada masalah integritas data yang belum terjelaskan.
