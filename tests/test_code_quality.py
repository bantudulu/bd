from app.domain import ACTIVE_ORDER_STATUSES, build_order_timeline, customer_status_label, normalize_order_status


def test_legacy_diproses_maps_to_waiting_customer_state():
    assert normalize_order_status("diproses") == "menunggu"
    assert customer_status_label("diproses") == "Menunggu Petugas"


def test_all_operational_statuses_are_active():
    assert {"menunggu", "ditugaskan", "menuju_lokasi", "dimulai"}.issubset(ACTIVE_ORDER_STATUSES)


def test_order_timeline_marks_previous_steps_done():
    timeline = build_order_timeline("menuju_lokasi")
    states = {item["key"]: item["state"] for item in timeline}
    assert states["menunggu"] == "done"
    assert states["ditugaskan"] == "done"
    assert states["menuju_lokasi"] == "current"
    assert states["dimulai"] == "upcoming"


def test_cancelled_timeline_does_not_fake_completion():
    timeline = build_order_timeline("dibatalkan")
    assert timeline[0]["state"] == "current"
    assert all(item["state"] != "done" for item in timeline)
