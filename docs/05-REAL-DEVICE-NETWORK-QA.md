# 5. Real Device & Weak Network QA

## Perangkat minimum
- Android kelas menengah/bawah.
- Chrome mobile.
- Wi-Fi normal.
- 4G/seluler yang tidak stabil.

## Jalur uji
1. `/masuk`
2. `/beranda`
3. buka layanan
4. buat order
5. `/pesanan`
6. detail pesanan
7. logout/login ulang

Gunakan `python scripts/network_smoke.py https://bantudulu.vercel.app` untuk baseline HTTP.
