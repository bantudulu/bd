# BantuDulu Android API v1

Dokumen ini mengunci kontrak backend untuk client Android BantuDulu. API Android memakai prefix `/api/v1` dan tidak menggantikan endpoint web lama.

## Authentication

### Login
`POST /api/v1/auth/login`

Body:
```json
{
  "email": "user@example.com",
  "password": "secret",
  "device_id": "android-installation-id",
  "device_name": "Samsung SM-S928B"
}
```

Response sukses selalu berbentuk:
```json
{
  "ok": true,
  "data": {}
}
```

Login mengembalikan `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in`, dan `session_id`.

- Access token berlaku 15 menit.
- Refresh session berlaku 30 hari.
- Refresh token dirotasi setiap kali dipakai.
- Database hanya menyimpan SHA-256 hash refresh token, bukan token mentah.
- Android menyimpan token menggunakan Android Keystore/EncryptedSharedPreferences atau mekanisme secure storage yang setara, bukan plain SharedPreferences.

### Refresh
`POST /api/v1/auth/refresh`

```json
{"refresh_token":"..."}
```

Client harus mengganti access + refresh token lokal dengan pasangan token baru dari response.

### Logout
`POST /api/v1/auth/logout`

Header:
`Authorization: Bearer <access_token>`

Logout mencabut mobile session di server.

## Error contract

Untuk `/api/v1/*`, HTTP error menggunakan bentuk:
```json
{
  "ok": false,
  "error": {
    "code": "unauthorized",
    "message": "Access token tidak valid atau sudah kedaluwarsa."
  }
}
```

Validation error dapat memiliki `fields`.

## Services

- `GET /api/v1/services`
- `GET /api/v1/services/{service_id}`

Katalog, jenis layanan, varian, form field, dan harga bersumber dari katalog final backend. Android tidak boleh menyimpan harga sebagai source of truth.

## Orders

- `GET /api/v1/orders`
- `GET /api/v1/orders/{id-or-code}`
- `POST /api/v1/orders`

### Idempotency

Setiap `POST /api/v1/orders` wajib mengirim header unik:

`Idempotency-Key: <8-100 chars>`

Satu key hanya boleh dipakai untuk satu payload. Retry jaringan dengan key + payload yang sama mengembalikan order yang sama dan tidak membuat duplikat baru.

Android harus membuat key sebelum request pertama dan mempertahankan key tersebut selama retry untuk aksi order yang sama.

### Order status

Flow customer final:

1. `menunggu` — Menunggu Petugas
2. `ditugaskan` — Petugas Ditugaskan
3. `menuju_lokasi` — Menuju Lokasi
4. `dimulai` — Sedang Dikerjakan
5. `selesai` — Selesai

Terminal alternatif: `dibatalkan`.

## Deep link

Order response dan notification response menggunakan kontrak:

`bantudulu://orders/{ORDER_CODE}`

Contoh:

`bantudulu://orders/BD-12AB34CD`

Android navigation harus membuka halaman detail/tracking order yang sesuai. Deep link tidak menggantikan authorization: client tetap harus login dan backend tetap memeriksa ownership order.

## Notifications and FCM device registration

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `PUT /api/v1/notifications/{id}/read`
- `POST /api/v1/devices`
- `DELETE /api/v1/devices/{id}`

`POST /api/v1/devices` menerima token FCM Android. Fase 9 hanya mengunci registrasi device dan payload/deep-link contract. Outbound Firebase Admin SDK, retry delivery, delivery log, dan invalid-token cleanup dilakukan pada integration/production phase.

## Network behavior

Android harus memperlakukan request GET sebagai retryable pada timeout/network failure. POST create-order hanya boleh di-retry menggunakan `Idempotency-Key` yang sama. Jangan membuat key baru hanya karena response pertama tidak diterima.

401 pada access token harus memicu satu refresh attempt. Jika refresh juga 401, hapus credential lokal dan arahkan user ke login.

## Security notes

- Jangan log access token, refresh token, password, atau FCM token ke production logs.
- TLS/HTTPS wajib untuk production.
- Web cookie auth dan Android bearer auth adalah dua jalur berbeda tetapi menggunakan user/customer yang sama.
- Petugas tetap bukan akun Android pada MVP.
