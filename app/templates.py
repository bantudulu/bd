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


def render(name: str, **context) -> HTMLResponse:
    template = env.get_template(name)
    html = template.render(**context)
    html = _remove_phone_mockup(name, html)
    return HTMLResponse(html)
