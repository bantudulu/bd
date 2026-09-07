from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.templates import render

router = APIRouter(tags=["operational-pages-v1"])


def _user(request: Request):
    return request.state.user


def _admin(request: Request):
    user = request.state.user
    return user if user and user.get("role") == "ADMIN" else None


@router.get("/pesanan")
async def customer_orders_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/masuk")
    if user.get("role") == "ADMIN":
        return RedirectResponse("/admin/pesanan")
    return render("customer/pesanan_operational.html", user=user)


@router.get("/pesanan/{order_id}")
async def customer_order_detail_page(request: Request, order_id: str):
    user = _user(request)
    if not user:
        return RedirectResponse("/masuk")
    if user.get("role") == "ADMIN":
        return RedirectResponse(f"/admin/pesanan/{order_id}")
    return render(
        "customer/pesanan_detail_operational.html",
        user=user,
        order_id=order_id,
    )


@router.get("/admin/dashboard")
async def admin_dashboard_page(request: Request):
    if not _admin(request):
        return RedirectResponse("/masuk")
    return render("admin/operational_dashboard.html", user=request.state.user)


@router.get("/admin/pesanan")
@router.get("/admin/kelola")
async def admin_orders_page(request: Request):
    if not _admin(request):
        return RedirectResponse("/masuk")
    return render("admin/operational_orders.html", user=request.state.user)


@router.get("/admin/pesanan/{order_id}")
async def admin_order_detail_page(request: Request, order_id: str):
    if not _admin(request):
        return RedirectResponse("/masuk")
    return render(
        "admin/operational_order_detail.html",
        user=request.state.user,
        order_id=order_id,
    )


@router.get("/admin/mitra")
async def admin_partners_page(request: Request):
    if not _admin(request):
        return RedirectResponse("/masuk")
    return render("admin/operational_mitra.html", user=request.state.user)


@router.get("/admin/layanan")
async def admin_catalog_page(request: Request):
    if not _admin(request):
        return RedirectResponse("/masuk")
    return render("admin/operational_layanan.html", user=request.state.user)
