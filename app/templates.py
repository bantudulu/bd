from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.responses import HTMLResponse

env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def format_rupiah(value):
    """Format number to IDR, e.g., 50000 → 50.000"""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

env.filters["formatrupiah"] = format_rupiah

def render(name: str, **context) -> HTMLResponse:
    template = env.get_template(name)
    return HTMLResponse(template.render(**context))
