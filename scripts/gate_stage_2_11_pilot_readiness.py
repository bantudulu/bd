from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print("STAGE 2-11 GATE FAIL:", msg)
    raise SystemExit(1)


def text(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        fail(f"missing {rel}")
    return p.read_text(encoding="utf-8")


py_files = [
    "app/routers/final_api.py",
    "app/routers/final_pages.py",
    "app/routers/operational.py",
    "app/routers/readiness.py",
    "app/auth.py",
    "app/security.py",
]
for rel in py_files:
    ast.parse(text(rel))
print("PYTHON SYNTAX: PASS")

final_api = text("app/routers/final_api.py")
final_pages = text("app/routers/final_pages.py")
category = text("app/templates/customer/category_special.html")
checkout = text("app/templates/customer/jadwal_pembayaran.html")
operational = text("app/routers/operational.py")
admin_detail = text("app/templates/admin/operational_order_detail.html")
config = text("app/config.py")
auth = text("app/auth.py")
security = text("app/security.py")
readiness = text("app/routers/readiness.py")

checks = {
    "Tukang Ringan/Berat UI": all(x in category for x in ["level-option", "work_level", "data-level-price"]),
    "Tukang price DB authoritative": all(x in final_api for x in ["_tukang_unit_price", '"Umum"', 'extras["work_level"]']),
    "Pijat distance admin-only": all(x in operational for x in ["/distance", "_distance_surcharge", "math.ceil", "confirmed_by_admin"]),
    "Pijat customer distance fields stripped": all(x in final_api for x in ['extras.pop("distance_km"', 'extras.pop("distance_surcharge"', '"confirmed_by_admin": False']),
    "Pijat previous surcharge trusted only after Admin": 'previous_policy.get("confirmed_by_admin") is True' in operational,
    "Pijat malformed surcharge safe": "_safe_nonnegative_int" in operational,
    "Pijat paid guard": "setelah pembayaran selesai" in operational,
    "Pijat customer notification": "Ongkos jarak dikonfirmasi" in operational,
    "Admin distance control": "Konfirmasi / Ubah Jarak" in admin_detail,
    "New order admin notification": "Pesanan baru BantuDulu" in final_api,
    "Legacy order route retired": 'legacy_pesan_redirect' in final_pages and 'RedirectResponse("/layanan"' in final_pages,
    "COD pilot only defaults": 'PAYMENT_BANK_ENABLED = env_bool("PAYMENT_BANK_ENABLED", False)' in config and 'PAYMENT_QRIS_ENABLED = env_bool("PAYMENT_QRIS_ENABLED", False)' in config,
    "Auth JWT claims": all(x in auth for x in ['"exp"', '"iss"', '"aud"', 'httponly=True']),
    "Auth abuse controls": all(x in security for x in ["login_limiter", "register_limiter", "reject_honeypot", "verify_turnstile"]),
    "Operational state machine": all(x in operational for x in ["/accept", "/assign", "/partner-accept", "/on-the-way", "/work-started", "/work-reported", "/complete"]),
    "Admin completion confirmation": "work_confirmed" in operational and "payment_confirmed" in operational,
    "Mitra service coverage enforced": "Mitra belum terdaftar untuk layanan pesanan ini" in operational,
    "Readiness blocks uncovered services": "service_coverage" in readiness and "ready_for_pilot" in readiness,
    "Checkout carries Tukang severity": "extras.work_level" in checkout,
    "Checkout carries Pijat distance policy": "extras.distance_policy" in checkout,
}
for name, ok in checks.items():
    if not ok:
        fail(name)
    print(name + ": PASS")

# Existing regression gates remain mandatory.
for script in [
    "scripts/gate_frontend_price_fix_v1.py",
    "scripts/gate_operational_v1.py",
    "scripts/gate_readiness_1_8.py",
]:
    result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
    if result.returncode != 0:
        fail(f"existing gate failed: {script}")

print("BANTUDULU STAGE 2-9 TECHNICAL GATE: PASS")
print("STAGE 10 REAL E2E: REQUIRES ONE REAL POST-CUTOFF ORDER")
print("STAGE 11 PILOT: REQUIRES /admin/readiness ready_for_pilot=true AND 3-5 REAL CUSTOMERS")
