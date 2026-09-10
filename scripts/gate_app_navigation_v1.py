from pathlib import Path
import ast
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print("APP NAVIGATION V1 GATE: FAIL -", message)
    raise SystemExit(1)


templates_py = (ROOT / "app/templates.py").read_text(encoding="utf-8")
main_py = (ROOT / "app/main.py").read_text(encoding="utf-8-sig")
nav_js = (ROOT / "app/static/nav/app-nav-v1.js").read_text(encoding="utf-8")
nav_css = (ROOT / "app/static/nav/app-nav-v1.css").read_text(encoding="utf-8")

for path in (
    ROOT / "app/templates.py",
    ROOT / "app/main.py",
    ROOT / "scripts/gate_app_navigation_v1.py",
):
    ast.parse(path.read_text(encoding="utf-8-sig"))

expected_views = (
    '"customer/beranda.html": "home"',
    '"customer/cari.html": "search"',
    '"customer/pesanan_operational.html": "orders"',
    '"customer/profil.html": "profile"',
)
if not all(token in templates_py for token in expected_views):
    fail("safe view allowlist berubah atau tidak lengkap")

for token in (
    'data-bd-page-style="1"',
    'data-bd-app-root="1"',
    'data-bd-bottom-nav="1"',
    'meta name="bd-app-nav" content="v1"',
    '/static/nav/app-nav-v1.css',
    '/static/nav/app-nav-v1.js',
    "Fail closed",
):
    if token not in templates_py:
        fail(f"renderer marker missing: {token}")

for token in (
    'path.startswith("/static/nav/")',
    '"public, max-age=31536000, immutable"',
    'response.headers.pop("Pragma", None)',
):
    if token not in main_py:
        fail(f"static navigation cache contract missing: {token}")

if 'path.startswith("/api/")' not in main_py or '"no-store, max-age=0"' not in main_py:
    fail("private/API no-store contract changed")

required_js = (
    "const SAFE_PATHS = new Set(['/beranda', '/cari', '/layanan', '/pesanan', '/profil'])",
    "data-bd-app-root",
    "data-bd-bottom-nav",
    "style[data-bd-page-style]",
    "currentRoot.replaceChildren",
    "history.pushState",
    "window.addEventListener('popstate'",
    "cache: 'no-store'",
    "credentials: 'same-origin'",
    "requestIdleCallback",
    "pointerover",
    "touchstart",
    "window.location.assign",
    "pageCache.clear()",
    "sequence !== navigationSequence",
    "IDLE_PREFETCH_PATHS",
    "PARTIAL_SOURCE_VIEWS",
    "canPartialFromCurrentView",
)
for token in required_js:
    if token not in nav_js:
        fail(f"navigation runtime contract missing: {token}")

for forbidden in ("localStorage", "sessionStorage", "caches.open(", "caches.match("):
    if forbidden in nav_js:
        fail(f"private HTML must not use persistent browser cache: {forbidden}")

if ".app-shell{" in nav_css or ".hero{" in nav_css or ".content{" in nav_css:
    fail("shared navigation CSS must not override approved page layout")
if "pointer-events: none" in nav_css:
    fail("loading state must not trap bottom navigation")
if "data-bd-nav-parking" in nav_js or "PARK_TTL_MS" in nav_js:
    fail("navigation runtime must not retain hidden page clones")
if "IDLE_PREFETCH_PATHS" not in nav_js or "'/beranda'" in nav_js.split("IDLE_PREFETCH_PATHS", 1)[1].split(";", 1)[0]:
    fail("idle prefetch must not warm DB-backed /beranda")
if "window.location.replace" not in nav_js:
    fail("history-safe full-load fallback missing")
if "const PARTIAL_SOURCE_VIEWS = new Set(['home', 'search'])" not in nav_js:
    fail("partial navigation must originate only from lifecycle-safe static views")
if nav_js.count("if (!canPartialFromCurrentView()) return;") < 4:
    fail("dynamic-view click/prefetch lifecycle guard incomplete")
if "if (!isSafeUrl(url) || !canPartialFromCurrentView())" not in nav_js:
    fail("popstate must full-reload when leaving a dynamic view")
if "fallbackNavigate(entry.responseUrl || url.href, {replace: historyMode === 'pop'})" not in nav_js:
    fail("document-validation fallback must preserve popstate history")
if "fallbackNavigate(finalUrl.href, {replace: historyMode === 'pop'})" not in nav_js:
    fail("style/shell fallback must preserve popstate history")
if "finalUrl.hash = url.hash" not in nav_js:
    fail("cross-page hash preservation missing")

# Isolated renderer-helper smoke test.
# Do not import app.templates here: the user's plain local Python may not have
# production dependencies installed. Extract only the navigation helper AST,
# then execute it against the four approved source templates.
templates_ast = ast.parse(templates_py)
isolated_nodes = []
for node in templates_ast.body:
    if isinstance(node, ast.Assign):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "_APP_NAV_VIEWS" in names:
            isolated_nodes.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name == "_enable_app_navigation":
        isolated_nodes.append(node)

if len(isolated_nodes) != 2:
    fail("cannot isolate navigation renderer helper")

isolated_module = ast.Module(body=isolated_nodes, type_ignores=[])
ast.fix_missing_locations(isolated_module)
isolated_ns = {}
exec(compile(isolated_module, "app/templates.py:navigation-helper", "exec"), isolated_ns)
enable_nav = isolated_ns["_enable_app_navigation"]

for name in (
    "customer/beranda.html",
    "customer/cari.html",
    "customer/pesanan_operational.html",
    "customer/profil.html",
):
    source_html = (ROOT / "app/templates" / name).read_text(encoding="utf-8")
    html = enable_nav(name, source_html)
    for token in (
        'data-bd-app-root="1"',
        'data-bd-bottom-nav="1"',
        'data-bd-page-style="1"',
        'meta name="bd-app-nav" content="v1"',
        '/static/nav/app-nav-v1.css',
        '/static/nav/app-nav-v1.js',
    ):
        if token not in html:
            fail(f"{name} helper output missing {token}")

node = subprocess.run(
    ["node", "--check", str(ROOT / "app/static/nav/app-nav-v1.js")],
    text=True,
    capture_output=True,
)
if node.returncode != 0:
    print(node.stdout)
    print(node.stderr)
    fail("navigation JavaScript syntax")

print("NAV 1 PERSISTENT APP SHELL: PASS")
print("NAV 2 PARTIAL NAVIGATION + FULL-LOAD FALLBACK: PASS")
print("NAV 3 SHARED NAVIGATION CSS: PASS")
print("NAV 4 SHARED JS RUNTIME + HISTORY: PASS")
print("NAV 5 TOUCH/HOVER/IDLE PREFETCH: PASS")
print("NAV 6 PRIVATE HTML NO-STORE + MEMORY-ONLY CACHE: PASS")
print("BANTUDULU APP NAVIGATION V1 GATE: PASS")
