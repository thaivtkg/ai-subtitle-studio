import unittest

from core.demo_capture.errors import CaptureRunError
from core.demo_capture.frame_clock import FrameClock


class TestDemoCaptureFrameClockC4(unittest.TestCase):
    def setUp(self):
        self.time = 0.0
        self.clock = FrameClock(10, lambda: self.time)

    def test_tc214_slots_yield_on_boundaries(self):
        self.clock.start()
        self.time = 0.05
        self.assertEqual(self.clock.due_count(), 0)
        self.time = 0.1
        self.assertEqual(self.clock.due_count(), 1)
        self.time = 0.15
        self.assertEqual(self.clock.due_count(), 0)

    def test_tc215_delayed_tick_yields_multiple_slots(self):
        self.clock.start()
        self.time = 0.35
        self.assertEqual(self.clock.due_count(), 3)
        self.time = 0.45
        self.assertEqual(self.clock.due_count(), 1)

    def test_tc216_backward_clock_fails(self):
        self.clock.start()
        self.time = -0.1
        with self.assertRaises(CaptureRunError):
            self.clock.due_count()


if __name__ == "__main__":
    unittest.main()
