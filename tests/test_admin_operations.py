import unittest

from app.routers.admin_assignment import STATUS_TRANSITIONS


class AdminOperationsTests(unittest.TestCase):
    def test_waiting_order_cannot_skip_to_on_the_way(self):
        self.assertNotIn("menuju_lokasi", STATUS_TRANSITIONS["menunggu"])

    def test_assigned_order_can_move_to_on_the_way(self):
        self.assertIn("menuju_lokasi", STATUS_TRANSITIONS["ditugaskan"])

    def test_on_the_way_can_start_work(self):
        self.assertIn("dimulai", STATUS_TRANSITIONS["menuju_lokasi"])

    def test_started_order_can_only_finish(self):
        self.assertEqual(STATUS_TRANSITIONS["dimulai"], {"selesai"})

    def test_terminal_states_have_no_next_state(self):
        self.assertEqual(STATUS_TRANSITIONS["selesai"], set())
        self.assertEqual(STATUS_TRANSITIONS["dibatalkan"], set())


if __name__ == "__main__":
    unittest.main()
