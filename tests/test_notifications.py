import unittest
from types import SimpleNamespace

from app.notification_service import STATUS_NOTIFICATION_COPY


class NotificationLifecycleTests(unittest.TestCase):
    def test_operational_statuses_have_customer_copy(self):
        self.assertIn("menuju_lokasi", STATUS_NOTIFICATION_COPY)
        self.assertIn("dimulai", STATUS_NOTIFICATION_COPY)
        self.assertIn("selesai", STATUS_NOTIFICATION_COPY)
        self.assertIn("dibatalkan", STATUS_NOTIFICATION_COPY)

    def test_copy_renders_order_code(self):
        code = "BD-ABC12345"
        for _status, (_title, message) in STATUS_NOTIFICATION_COPY.items():
            rendered = message.format(kode=code)
            self.assertIn(code, rendered)


if __name__ == "__main__":
    unittest.main()
