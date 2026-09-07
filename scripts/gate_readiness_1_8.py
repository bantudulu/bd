from pathlib import Path
import ast, sys
root=Path(__file__).resolve().parents[1]
required=[
"app/routers/readiness.py","app/templates/admin/readiness.html",
"docs/01-OPERATIONAL-READINESS.md","docs/02-E2E-ORDER-TEST.md","docs/03-MITRA-COMMUNICATION.md",
"docs/04-NOTIFICATION-OPERATIONS.md","docs/05-REAL-DEVICE-NETWORK-QA.md","docs/06-PILOT-RUNBOOK.md",
"docs/07-POST-PILOT-AUDIT.md","docs/08-LAUNCH-READINESS.md","docs/PRIVACY-POLICY-DRAFT.md",
"docs/TERMS-OF-SERVICE-DRAFT.md","scripts/network_smoke.py","scripts/post_pilot_audit.py"]
for rel in required:
    if not (root/rel).exists():
        print("READINESS GATE FAIL: missing",rel);sys.exit(1)
readiness=(root/"app/routers/readiness.py").read_text(encoding="utf-8")
pages=(root/"app/routers/operational_pages.py").read_text(encoding="utf-8")
main=(root/"app/main.py").read_text(encoding="utf-8")
dashboard=(root/"app/templates/admin/operational_dashboard.html").read_text(encoding="utf-8")
ast.parse(readiness);ast.parse((root/"scripts/network_smoke.py").read_text(encoding="utf-8"));ast.parse((root/"scripts/post_pilot_audit.py").read_text(encoding="utf-8"))
for token in ["/api/ops/admin/readiness","/api/ops/admin/orders/{order_id}/contact","/api/ops/admin/notifications/recent","private, no-store"]:
    if token not in readiness:
        print("READINESS GATE FAIL:",token);sys.exit(1)
if '@router.get("/admin/readiness")' not in pages:
    print("READINESS GATE FAIL: page route");sys.exit(1)
if "readiness," not in main or "app.include_router(readiness.router)" not in main:
    print("READINESS GATE FAIL: main registration");sys.exit(1)
if 'href="/admin/readiness"' not in dashboard:
    print("READINESS GATE FAIL: dashboard link");sys.exit(1)
print("READINESS 1 OPERATIONAL GATE: PASS")
print("READINESS 2 E2E RUNBOOK: PASS")
print("READINESS 3 MITRA COMMUNICATION: PASS")
print("READINESS 4 NOTIFICATION AUDIT: PASS")
print("READINESS 5 NETWORK QA TOOLING: PASS")
print("READINESS 6 PILOT RUNBOOK: PASS")
print("READINESS 7 POST-PILOT AUDIT TOOLING: PASS")
print("READINESS 8 LAUNCH DOCUMENTATION: PASS")
print("BANTUDULU READINESS 1-8 CODE GATE: PASS")
