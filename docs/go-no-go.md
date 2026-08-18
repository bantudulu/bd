# BantuDulu — Production Deployment Rehearsal & GO / NO-GO

Dokumen ini adalah gate terakhir sebelum public production traffic.

## Automated rehearsal

CI harus lulus seluruh validation dari Fase 12 dan end-to-end rehearsal berikut:

1. customer mobile login;
2. customer membuat order dengan `Idempotency-Key`;
3. admin assign petugas;
4. status bergerak `ditugaskan → menuju_lokasi → dimulai → selesai`;
5. customer membaca order final beserta petugas aktif;
6. customer menerima notifikasi yang terkait order.

Automated rehearsal memakai database test terisolasi. Lulusnya rehearsal membuktikan source dan flow terintegrasi, bukan membuktikan infrastruktur production siap.

## Public production evidence

Sebelum GO, operator wajib mempunyai bukti untuk seluruh gate:

- CI release hijau;
- migration rehearsal sukses;
- customer-to-admin journey sukses;
- backup production/staging berhasil direstore ke database terpisah dan dibaca aplikasi;
- secret production fresh dan tidak pernah tersimpan di Git;
- database production tidak mengandung akun demo/default legacy;
- `/health/live` dan `/health/ready` pada deployment target HTTP 200;
- domain, TLS, dan reverse proxy final aktif;
- operator telah membaca dan memahami backup, rollback, dan incident runbook.

## Decision command

Setelah bukti nyata diverifikasi, set evidence flags hanya untuk item yang benar-benar sudah dibuktikan lalu jalankan:

```bash
EVIDENCE_CI_GREEN=true \
EVIDENCE_MIGRATION_REHEARSAL=true \
EVIDENCE_CUSTOMER_ADMIN_JOURNEY=true \
EVIDENCE_BACKUP_RESTORE_REHEARSAL=true \
EVIDENCE_FRESH_PRODUCTION_SECRETS=true \
EVIDENCE_NO_LEGACY_DEMO_ACCOUNTS=true \
EVIDENCE_PRODUCTION_HEALTH_READY=true \
EVIDENCE_DOMAIN_TLS_REVERSE_PROXY=true \
EVIDENCE_OPERATOR_RUNBOOK_REVIEWED=true \
python -m scripts.go_no_go
```

Command exit `0` hanya jika semua gate PASS. Bila satu saja evidence tidak ada, decision adalah `NO-GO` dan process exit non-zero.

Jangan mengubah evidence menjadi `true` hanya untuk membuat command hijau. Evidence adalah catatan hasil verifikasi operasional nyata.

## Deployment rehearsal order

1. Freeze release SHA.
2. Backup database target.
3. Restore backup ke database rehearsal terpisah dan validasi data dapat dibaca.
4. Jalankan migration pada rehearsal database.
5. Jalankan aplikasi release SHA dengan konfigurasi yang setara production.
6. Cek live/readiness.
7. Jalankan customer-to-admin smoke journey.
8. Verifikasi log tidak membocorkan credential/token.
9. Uji rollback aplikasi ke release sehat terakhir.
10. Lengkapi GO/NO-GO evidence.

## Current rule

Tanpa akses/bukti dari database production, backup storage, secret manager, domain/TLS, dan deployment target, keputusan public production harus tetap **NO-GO**, walaupun CI dan automated rehearsal hijau.
