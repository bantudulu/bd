from pathlib import Path
import ast
import re
import sys

root = Path(__file__).resolve().parents[1]
op = (root / "app/routers/operational.py").read_text(encoding="utf-8")
customer = (root / "app/templates/customer/pesanan_operational.html").read_text(encoding="utf-8")
admin = (root / "app/templates/admin/operational_orders.html").read_text(encoding="utf-8")

def fail(msg):
    print("PERFORMANCE GATE: FAIL -", msg)
    sys.exit(1)

ast.parse(op)

def block(start, end):
    i = op.find(start)
    j = op.find(end, i + 1)
    if i < 0 or j < 0:
        fail(f"block marker missing: {start}")
    return op[i:j]

cust = block('@router.get("/api/ops/customer/orders")', '@router.get("/api/ops/customer/orders/{order_id}")')
admin_list = block('@router.get("/api/ops/admin/orders")', '@router.get("/api/ops/admin/orders/{order_id}")')
summary = block('@router.get("/api/ops/admin/summary")', '@router.get("/api/ops/admin/orders")')

if "outerjoin(Layanan" not in cust or "outerjoin(LayananVarian" not in cust:
    fail("customer list is not joined")
if "await db.get(" in cust:
    fail("customer list still has N+1 db.get")
if ".limit(page_size)" not in cust or '"has_more"' not in cust:
    fail("customer pagination missing")

if "_order_admin_payload" in admin_list or "await db.get(" in admin_list:
    fail("admin list still uses per-order loader")
for token in (
    "PenugasanMitra.pesanan_id.in_(order_ids)",
    "PaymentTransaction.pesanan_id.in_(order_ids)",
    ".limit(page_size)",
    '"has_more"',
):
    if token not in admin_list:
        fail(f"admin batched pagination missing: {token}")

if "case(" not in summary:
    fail("SQL aggregate CASE missing")
if "select(Pesanan)).scalars().all()" in summary:
    fail("summary still loads all orders")

for token in ("private, no-store", 'response.headers["Vary"] = "Cookie"'):
    if token not in op:
        fail(f"private cache protection missing: {token}")

for name, text in (("customer", customer), ("admin", admin)):
    if "loadMore" not in text or "page_size" not in text:
        fail(f"{name} progressive pagination missing")
    no_store_fetch = (
        "cache:'no-store'" in text
        or 'cache:"no-store"' in text
        or "opts.cache='no-store'" in text
        or 'opts.cache="no-store"' in text
    )
    if not no_store_fetch:
        fail(f"{name} no-store fetch missing")

if "async function refreshOrder" not in admin:
    fail("single-order refresh missing")
if "await load(" in admin:
    fail("admin action still reloads whole list")
if "await refreshOrder(id)" not in admin:
    fail("admin actions do not refresh single order")

print("PERF 1 N+1 REMOVAL: PASS")
print("PERF 2 SQL AGGREGATE DASHBOARD: PASS")
print("PERF 3 PAGINATION + LOAD MORE: PASS")
print("PERF 4 SINGLE-ORDER REFRESH: PASS")
print("PERF 5 PRIVATE NO-STORE: PASS")
print("BANTUDULU PERFORMANCE GATE: PASS")
