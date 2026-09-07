from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_FILES = [
    ROOT / "app/routers/operational.py",
    ROOT / "app/routers/operational_pages.py",
]
HTML_FILES = [
    ROOT / "app/templates/customer/pesanan_operational.html",
    ROOT / "app/templates/customer/pesanan_detail_operational.html",
    ROOT / "app/templates/admin/operational_dashboard.html",
    ROOT / "app/templates/admin/operational_orders.html",
    ROOT / "app/templates/admin/operational_order_detail.html",
    ROOT / "app/templates/admin/operational_mitra.html",
    ROOT / "app/templates/admin/operational_layanan.html",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def check_python() -> None:
    for path in PY_FILES:
        if not path.exists():
            fail(f"missing {path.relative_to(ROOT)}")
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("PYTHON OPERATIONAL COMPILE: PASS")


def check_html() -> None:
    for path in HTML_FILES:
        if not path.exists():
            fail(f"missing {path.relative_to(ROOT)}")
        parser = HTMLParser()
        parser.feed(path.read_text(encoding="utf-8"))
    print("HTML PARSE GATE: PASS")


def check_js() -> None:
    try:
        subprocess.run(["node", "--version"], check=True, capture_output=True, text=True)
    except Exception:
        fail("Node.js tidak ditemukan untuk JavaScript syntax gate")

    for path in HTML_FILES:
        text = path.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S | re.I)
        js = "\n".join(scripts)
        js = js.replace("{{ order_id|tojson }}", '"qa-order"')
        if not js.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as fh:
            fh.write(js)
            temp = fh.name
        result = subprocess.run(["node", "--check", temp], capture_output=True, text=True)
        Path(temp).unlink(missing_ok=True)
        if result.returncode:
            fail(f"JavaScript syntax {path.name}: {result.stderr.strip()}")
    print("JAVASCRIPT SYNTAX GATE: PASS")


def check_contract() -> None:
    op = (ROOT / "app/routers/operational.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    customer = (
        (ROOT / "app/templates/customer/pesanan_operational.html").read_text(encoding="utf-8")
        + (ROOT / "app/templates/customer/pesanan_detail_operational.html").read_text(encoding="utf-8")
    )
    admin = (
        (ROOT / "app/templates/admin/operational_orders.html").read_text(encoding="utf-8")
        + (ROOT / "app/templates/admin/operational_mitra.html").read_text(encoding="utf-8")
        + (ROOT / "app/templates/admin/operational_layanan.html").read_text(encoding="utf-8")
    )

    required = [
        '/api/ops/admin/orders/{order_id}/assign',
        '/api/ops/admin/orders/{order_id}/partner-reject',
        '/api/ops/admin/orders/{order_id}/work-reported',
        '/api/ops/admin/orders/{order_id}/complete',
        'work_confirmed',
        'payment_confirmed',
        'menunggu_konfirmasi',
        'Perubahan status bebas dinonaktifkan',
    ]
    for token in required:
        if token not in op:
            fail(f"operational contract missing: {token}")

    banned_customer = [
        "Mitra menuju",
        "Mencari mitra",
        "Hubungi mitra",
        "mitra terdekat",
    ]
    for token in banned_customer:
        if token.casefold() in customer.casefold():
            fail(f"customer UI masih membocorkan proses internal: {token}")

    required_customer = [
        "Pesanan diterima BantuDulu",
        "Tim BantuDulu sedang menuju lokasi",
        "Selesai",
    ]
    for token in required_customer:
        if token.casefold() not in (op + customer).casefold():
            fail(f"customer public status missing: {token}")

    fake_names = ["Arif Rahman", "Maya Nur", "Irfan Syam", "Rizal Kadir", "Nadia Aulia", "Dewa Web"]
    for name in fake_names:
        if name in admin:
            fail(f"fake admin data masih aktif: {name}")

    if "read-only" not in admin.lower():
        fail("admin catalog must be explicitly read-only for V1 pilot")

    if "operational_pages.router" not in main or "operational.router" not in main:
        fail("operational routers belum terpasang di app/main.py")

    pos_pages = main.find("app.include_router(operational_pages.router)")
    pos_final_pages = main.find("app.include_router(final_pages.router)")
    pos_op = main.find("app.include_router(operational.router)")
    pos_api = main.find("app.include_router(api.router)")
    if min(pos_pages, pos_final_pages, pos_op, pos_api) < 0:
        fail("router include order tidak lengkap")
    if not (pos_pages < pos_final_pages and pos_op < pos_api):
        fail("operational routers harus mendahului legacy page/API routers")

    legacy_required = [
        "_is_legacy_order",
        "Riwayat pesanan lama",
        "metode_pembayaran_label",
    ]
    for token in legacy_required:
        if token.casefold() not in (op + customer).casefold():
            fail(f"legacy customer detail handling missing: {token}")
    print("LEGACY ORDER DETAIL CONTRACT: PASS")

    print("STAGE 7 ORDER FLOW CONTRACT: PASS")
    print("STAGE 8 CUSTOMER TRACKING PRIVACY: PASS")
    print("STAGE 10 ADMIN REAL-DATA UI CONTRACT: PASS")


def check_responsive_contract() -> None:
    customer = (ROOT / "app/templates/customer/pesanan_operational.html").read_text(encoding="utf-8")
    admin = (ROOT / "app/templates/admin/operational_orders.html").read_text(encoding="utf-8")
    required_media = ["max-width:360px", "max-width:390px", "max-width:760px"]
    joined = customer.replace(" ", "") + admin.replace(" ", "")
    for token in required_media:
        if token not in joined:
            fail(f"responsive breakpoint missing: {token}")
    if "viewport-fit=cover" not in customer or "viewport-fit=cover" not in admin:
        fail("mobile safe-area viewport missing")
    if "env(safe-area-inset-bottom)" not in customer or "env(safe-area-inset-bottom)" not in admin:
        fail("safe-area bottom handling missing")
    print("STAGE 9 RESPONSIVE STATIC CONTRACT: PASS")


def main() -> None:
    check_python()
    check_html()
    check_js()
    check_contract()
    check_responsive_contract()
    print("BANTUDULU OPERATIONAL CODE GATE: PASS")


if __name__ == "__main__":
    main()
