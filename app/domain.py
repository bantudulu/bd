ORDER_STATUS_FLOW = (
    "menunggu",
    "ditugaskan",
    "menuju_lokasi",
    "dimulai",
    "selesai",
)

ACTIVE_ORDER_STATUSES = {
    "menunggu",
    "diproses",  # legacy compatibility
    "ditugaskan",
    "menuju_lokasi",
    "dimulai",
}

TERMINAL_ORDER_STATUSES = {"selesai", "dibatalkan"}
VALID_ORDER_STATUSES = ACTIVE_ORDER_STATUSES | TERMINAL_ORDER_STATUSES

CUSTOMER_STATUS_LABELS = {
    "menunggu": "Menunggu Petugas",
    "diproses": "Menunggu Petugas",
    "ditugaskan": "Petugas Ditugaskan",
    "menuju_lokasi": "Menuju Lokasi",
    "dimulai": "Sedang Dikerjakan",
    "selesai": "Selesai",
    "dibatalkan": "Dibatalkan",
}

ORDER_TIMELINE_STEPS = (
    ("menunggu", "Menunggu Petugas", "Pesanan sudah diterima dan tim BantuDulu sedang menyiapkan petugas."),
    ("ditugaskan", "Petugas Ditugaskan", "Petugas sudah ditentukan untuk pesanan Anda."),
    ("menuju_lokasi", "Menuju Lokasi", "Petugas sedang menuju alamat layanan."),
    ("dimulai", "Sedang Dikerjakan", "Layanan sedang dikerjakan oleh petugas."),
    ("selesai", "Selesai", "Pesanan selesai dikerjakan."),
)


def normalize_order_status(status: str | None) -> str:
    value = (status or "menunggu").strip().lower()
    return "menunggu" if value == "diproses" else value


def customer_status_label(status: str | None) -> str:
    value = (status or "menunggu").strip().lower()
    return CUSTOMER_STATUS_LABELS.get(value, value.replace("_", " ").title())


def build_order_timeline(status: str | None) -> list[dict]:
    normalized = normalize_order_status(status)
    rank = {key: index for index, (key, _, _) in enumerate(ORDER_TIMELINE_STEPS)}
    current_rank = rank.get(normalized, 0)
    return [
        {
            "key": key,
            "label": label,
            "description": description,
            "state": "done" if current_rank > index else "current" if current_rank == index else "upcoming",
        }
        for index, (key, label, description) in enumerate(ORDER_TIMELINE_STEPS)
    ]
