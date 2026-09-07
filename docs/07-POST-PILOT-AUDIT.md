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

Launch ditahan jika ada masalah integritas data yang belum terjelaskan.\n\n## Guard audit production\nAudit production wajib memakai DATABASE_URL PostgreSQL. Script berhenti dengan exit code 3 bila URL tidak tersedia/valid dan tidak boleh fallback ke SQLite. Audit integritas aktif hanya menilai order Operational V1; arsip lama tetap dilaporkan terpisah.\n