from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notifikasi, Pesanan


STATUS_NOTIFICATION_COPY = {
    "menuju_lokasi": (
        "Petugas sedang menuju lokasi",
        "Petugas BantuDulu sedang menuju lokasi untuk pesanan {kode}.",
    ),
    "dimulai": (
        "Pekerjaan dimulai",
        "Layanan untuk pesanan {kode} sudah dimulai.",
    ),
    "selesai": (
        "Pesanan selesai",
        "Pesanan {kode} telah selesai. Terima kasih sudah menggunakan BantuDulu.",
    ),
    "dibatalkan": (
        "Pesanan dibatalkan",
        "Pesanan {kode} telah dibatalkan.",
    ),
}


def add_order_notification(
    db: AsyncSession,
    *,
    order: Pesanan,
    title: str,
    message: str,
) -> Notifikasi:
    notification = Notifikasi(
        user_id=order.user_id,
        pesanan_id=order.id,
        judul=title,
        pesan=message,
    )
    db.add(notification)
    return notification


def add_status_notification(db: AsyncSession, *, order: Pesanan, status: str) -> Notifikasi | None:
    copy = STATUS_NOTIFICATION_COPY.get(status)
    if not copy:
        return None
    title, message = copy
    return add_order_notification(
        db,
        order=order,
        title=title,
        message=message.format(kode=order.kode),
    )
