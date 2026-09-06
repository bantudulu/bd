import os
from app.config import (
    DATABASE_URL,
    ENABLE_CATALOG_SYNC,
    ENABLE_DEMO_SEED,
    GOOGLE_CLIENT_ID,
    IS_PRODUCTION,
    MARKETPLACE_SCHEMA_ENABLED,
    PAYMENT_BANK_ENABLED,
    PAYMENT_QRIS_ENABLED,
    STARTUP_DB_INIT,
    TURNSTILE_ENABLED,
    USING_SQLITE,
)

checks = []

def add(name, ok, detail):
    checks.append((name, ok, detail))

add("SECRET_KEY", bool(os.getenv("SECRET_KEY")), "harus ada di environment")
add("Persistent DB", not (IS_PRODUCTION and USING_SQLITE), DATABASE_URL.split("@")[-1] if DATABASE_URL else "missing")
add("Startup schema mutation OFF", not (IS_PRODUCTION and STARTUP_DB_INIT), str(STARTUP_DB_INIT))
add("Demo seed OFF", not (IS_PRODUCTION and ENABLE_DEMO_SEED), str(ENABLE_DEMO_SEED))
add("Catalog sync OFF", not (IS_PRODUCTION and ENABLE_CATALOG_SYNC), str(ENABLE_CATALOG_SYNC))
add("Turnstile", TURNSTILE_ENABLED, "configured" if TURNSTILE_ENABLED else "optional until keys are set")
add("Google Login", bool(GOOGLE_CLIENT_ID), "configured" if GOOGLE_CLIENT_ID else "optional until Client ID is set")
add("Marketplace schema", MARKETPLACE_SCHEMA_ENABLED, str(MARKETPLACE_SCHEMA_ENABLED))
add("Bank payment", not PAYMENT_BANK_ENABLED, "keep disabled until gateway/reconciliation exists")
add("QRIS payment", not PAYMENT_QRIS_ENABLED, "keep disabled until gateway/reconciliation exists")

print("BANTUDULU PRODUCTION READINESS")
failed = 0
for name, ok, detail in checks:
    mark = "PASS" if ok else "WARN"
    print(f"{mark:4}  {name:28} {detail}")
    failed += 0 if ok else 1

raise SystemExit(0 if failed == 0 else 2)
