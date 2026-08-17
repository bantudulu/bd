from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.templates import render

router = APIRouter(tags=["notification-pages"])


@router.get("/notifikasi")
async def notifications_page(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse(url="/masuk")
    if user.get("role") != "CUSTOMER":
        return RedirectResponse(url="/admin/dashboard")
    return render("customer/notifikasi.html", user=user)
