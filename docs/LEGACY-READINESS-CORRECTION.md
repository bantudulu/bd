# BantuDulu Legacy / Readiness Correction

Perbaikan ini menutup lima temuan baseline production tanpa mengubah data lama.

A. Audit production fail-fast bila DATABASE_URL PostgreSQL tidak tersedia. Tidak boleh fallback ke SQLite.
B. Varian bernama arsip dengan harga Rp0 tetap dipertahankan untuk histori dan tidak menjadi blocker readiness.
C. Order sebelum Operational V1 (boundary 2026-09-07T06:29:07Z) diklasifikasikan eksplisit sebagai legacy/archive.
D. Legacy tidak dihitung sebagai order aktif, assignment readiness, atau active queue Admin/Customer.
E. Legacy tetap dapat dilihat sebagai histori, tetapi mutation Operational V1 diblokir.

Tidak ada migration/schema change. Tidak ada UPDATE/DELETE data production.
