import re

from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.responses import HTMLResponse

env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def format_rupiah(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


env.filters["formatrupiah"] = format_rupiah


def _remove_phone_mockup(name: str, html: str) -> str:
    if not name.startswith("customer/"):
        return html

    html = re.sub(
        r'\s*<div class="statusbar"[^>]*>.*?(?=<div class="brand-row">)',
        "\n",
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r'\s*<div class="status"[^>]*>.*?(?=<div class="title-row">)',
        "\n",
        html,
        count=1,
        flags=re.S,
    )

    cleanup = (
        '<style id="bd-remove-phone-mockup">'
        '.hero>.statusbar,.top>.status{display:none!important}'
        '</style>'
    )
    if "</head>" in html:
        html = html.replace("</head>", cleanup + "</head>", 1)
    return html




_APP_NAV_VIEWS = {
    "customer/beranda.html": "home",
    "customer/cari.html": "search",
    "customer/pesanan_operational.html": "orders",
    "customer/profil.html": "profile",
}


def _enable_app_navigation(name: str, html: str) -> str:
    view = _APP_NAV_VIEWS.get(name)
    if not view:
        return html

    root_marker = (
        '<div class="app-shell">'
        if '<div class="app-shell">' in html
        else '<div class="app">' if '<div class="app">' in html else None
    )
    nav_marker = (
        '<nav class="bottom-nav"'
        if '<nav class="bottom-nav"' in html
        else '<nav class="bottom"' if '<nav class="bottom"' in html else None
    )
    if not root_marker or not nav_marker or "<style>" not in html:
        # Fail closed: original full-page navigation remains untouched.
        return html

    html = html.replace(
        "<style>",
        '<style data-bd-page-style="1">',
        1,
    )
    html = html.replace(
        root_marker,
        root_marker[:-1] + ' data-bd-app-root="1">',
        1,
    )
    html = html.replace(
        nav_marker,
        nav_marker + ' data-bd-bottom-nav="1"',
        1,
    )

    head_assets = (
        f'<meta name="bd-app-nav" content="v1">'
        f'<meta name="bd-app-view" content="{view}">'
        '<link rel="stylesheet" href="/static/nav/app-nav-v1.css">'
    )
    html = html.replace("</head>", head_assets + "</head>", 1)
    html = html.replace(
        "</body>",
        '<script defer src="/static/nav/app-nav-v1.js"></script></body>',
        1,
    )
    return html

def render(name: str, **context) -> HTMLResponse:
    template = env.get_template(name)
    html = template.render(**context)
    html = _remove_phone_mockup(name, html)
    html = _enable_app_navigation(name, html)
    return HTMLResponse(html)
