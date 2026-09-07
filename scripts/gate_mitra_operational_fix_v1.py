from pathlib import Path
import re, sys

root = Path(__file__).resolve().parents[1]
models = (root / "app" / "models.py").read_text(encoding="utf-8-sig")
op = (root / "app" / "routers" / "operational.py").read_text(encoding="utf-8-sig")
html = (root / "app" / "templates" / "admin" / "operational_mitra.html").read_text(encoding="utf-8-sig")

def need(label, cond):
    if not cond:
        print(f"{label}: FAIL")
        raise SystemExit(1)
    print(f"{label}: PASS")

need("MITRA FIX 1 DB UTC-NAIVE DEFAULTS",
     'return datetime.now(timezone.utc).replace(tzinfo=None)' in models)
need("MITRA FIX 2 OPERATIONAL UTC-NAIVE WRITES",
     'def _utcnow_db() -> datetime:' in op
     and 'assignment.accepted_at = _utcnow_db()' in op
     and 'now = _utcnow_db()' in op)
need("MITRA FIX 3 CLEAN ADMIN UI",
     'Cakupan Layanan Aktif' in html
     and 'partner-grid' in html
     and 'modal-card' in html
     and 'form-error' in html)
need("MITRA FIX 4 REAL API ONLY",
     "/api/ops/admin/partners" in html
     and "/api/ops/admin/catalog" in html
     and "Rp38,4" not in html
     and "Arif Rahman" not in html)
need("MITRA FIX 5 EXPLICIT DOM + HTTP ERRORS",
     "getElementById" in html
     and "HTTP '+response.status" in html
     and "alert(" not in html)
need("MITRA FIX 6 NO AWARE DIRECT WRITES",
     op.count("datetime.now(timezone.utc)") == 1)

print("BANTUDULU MITRA OPERATIONAL FIX GATE: PASS")
