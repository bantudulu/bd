import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException

from app.routers.api_pesanan import (
    BUSINESS_TIMEZONE,
    _calculate_base_price,
    _calculate_form_price_and_validate,
    _extract_option_price,
    _parse_schedule,
)


class OrderPricingTests(unittest.TestCase):
    def test_per_jam_multiplies_variant_price(self):
        layanan = SimpleNamespace(tipe_hitung="per_jam")
        varian = SimpleNamespace(harga=60_000)
        self.assertEqual(_calculate_base_price(layanan, varian, 3), 180_000)

    def test_per_pekerjaan_does_not_multiply_duration(self):
        layanan = SimpleNamespace(tipe_hitung="per_pekerjaan")
        varian = SimpleNamespace(harga=500_000)
        self.assertEqual(_calculate_base_price(layanan, varian, 4), 500_000)

    def test_select_price_must_come_from_catalog_option(self):
        options = ["Standar", "Tambahan|30000"]
        self.assertEqual(_extract_option_price("Tambahan|30000", options), 30_000)
        with self.assertRaises(HTTPException):
            _extract_option_price("Tambahan|1", options)

    def test_checkbox_addon_uses_server_catalog_price(self):
        field = SimpleNamespace(
            id="abc",
            label="+ Refleksi",
            field_type="checkbox",
            options=None,
            required=False,
            harga_tambahan=30_000,
        )
        extra, sanitized = _calculate_form_price_and_validate(
            [field], {"field_abc": "on"}, 1
        )
        self.assertEqual(extra, 30_000)
        self.assertTrue(sanitized["field_abc"])

    def test_tandon_floor_fee_only_comes_from_lokasi_tandon_field(self):
        tandon_field = SimpleNamespace(
            id="loc",
            label="Lokasi Tandon",
            field_type="select",
            options=json.dumps(["Lantai 1", "Lantai 2+ (butuh bantuan)"]),
            required=True,
            harga_tambahan=None,
        )
        extra, _ = _calculate_form_price_and_validate(
            [tandon_field], {"field_loc": "Lantai 2+ (butuh bantuan)"}, 1
        )
        self.assertEqual(extra, 50_000)

        unrelated_field = SimpleNamespace(
            id="note",
            label="Catatan",
            field_type="text",
            options=None,
            required=True,
            harga_tambahan=None,
        )
        extra, _ = _calculate_form_price_and_validate(
            [unrelated_field], {"field_note": "Lantai 2+"}, 1
        )
        self.assertEqual(extra, 0)

    def test_unknown_dynamic_field_is_rejected(self):
        with self.assertRaises(HTTPException):
            _calculate_form_price_and_validate([], {"field_fake": "x"}, 1)

    def test_past_date_is_rejected(self):
        with self.assertRaises(HTTPException):
            _parse_schedule("2000-01-01", "09:00")

    def test_invalid_booking_interval_is_rejected(self):
        tomorrow = (datetime.now(BUSINESS_TIMEZONE) + timedelta(days=1)).date().isoformat()
        with self.assertRaises(HTTPException):
            _parse_schedule(tomorrow, "09:15")


if __name__ == "__main__":
    unittest.main()
