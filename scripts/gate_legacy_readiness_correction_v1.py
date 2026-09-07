from __future__ import annotations
import ast,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def fail(msg):
    print("CORRECTION GATE FAIL:",msg);raise SystemExit(1)

paths={
"policy":ROOT/"app/operational_policy.py",
"op":ROOT/"app/routers/operational.py",
"readiness":ROOT/"app/routers/readiness.py",
"audit":ROOT/"scripts/post_pilot_audit.py",
"admin":ROOT/"app/templates/admin/operational_orders.html",
}
for name,path in paths.items():
    if not path.exists():fail(f"missing {name}: {path}")
    if path.suffix==".py":ast.parse(path.read_text(encoding="utf-8"))

policy=paths["policy"].read_text(encoding="utf-8")
op=paths["op"].read_text(encoding="utf-8")
readiness=paths["readiness"].read_text(encoding="utf-8")
audit=paths["audit"].read_text(encoding="utf-8")
admin=paths["admin"].read_text(encoding="utf-8")

for token in ["OPERATIONAL_V1_CUTOFF_DB","2026, 9, 7, 6, 29, 7","is_pre_operational_v1"]:
    if token not in policy:fail("policy missing "+token)
for token in ["is_pre_operational_v1(order.created_at)","def _current_order_conditions","Pesanan.created_at >= OPERATIONAL_V1_CUTOFF_DB","Pesanan aktif lama/arsip tidak dapat diubah",'"is_legacy": _is_legacy_order(order)']:
    if token not in op:fail("operational missing "+token)
if op.count("conditions.extend(_current_order_conditions())")<4:fail("customer/admin active filters not fully scoped")
for token in ["legacy_archive_orders","archived_zero_price_variants_ignored",'like("%arsip%")',"*_current_order_conditions()"]:
    if token not in readiness:fail("readiness missing "+token)
for token in ["AUDIT ABORTED:","SQLite fallback tidak diizinkan","DATABASE_URL_RAW","legacy_archive_orders","archived_zero_price_variant_ignored","current_non_cod_payment_transactions"]:
    if token not in audit:fail("audit missing "+token)
if audit.find("DATABASE_URL_RAW")>audit.find("from app.database import async_session"):fail("fail-fast occurs after app import")
if "if(o.is_legacy)" not in admin or "Arsip — tidak dapat diubah" not in admin:fail("admin legacy action suppression missing")

env=os.environ.copy();env.pop("DATABASE_URL",None)
probe=subprocess.run([sys.executable,"-m","scripts.post_pilot_audit"],cwd=ROOT,env=env,capture_output=True,text=True)
combined=probe.stdout+probe.stderr
if probe.returncode!=3 or "AUDIT ABORTED:" not in combined:fail(f"missing-DB fail-fast rc={probe.returncode}")
if "sqlite3.OperationalError" in combined:fail("audit touched SQLite")

print("CORRECTION A DATABASE FAIL-FAST: PASS")
print("CORRECTION B ARCHIVED ZERO-PRICE EXCLUSION: PASS")
print("CORRECTION C PRE-V1 LEGACY CLASSIFICATION: PASS")
print("CORRECTION D LEGACY EXCLUDED FROM ACTIVE/READINESS: PASS")
print("CORRECTION E LEGACY MUTATION BLOCKED: PASS")
print("BANTUDULU LEGACY/READINESS CORRECTION GATE: PASS")
