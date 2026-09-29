import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from defend.rules import plan_appeal  # noqa: E402

NY = ZoneInfo("America/New_York")


class DefendRulesTest(unittest.TestCase):
    def test_deadline_is_noon_day_before(self):
        p = plan_appeal(date(2026, 10, 9), datetime(2026, 10, 7, 9, 0, tzinfo=NY))
        self.assertIn("October 8, 2026 at 12:00 noon", p.deadline_local)
        self.assertEqual(p.hours_left, 27.0)
        self.assertEqual(p.status, "on_time")

    def test_urgent_within_24h(self):
        p = plan_appeal(date(2026, 10, 9), datetime(2026, 10, 8, 8, 30, tzinfo=NY))
        self.assertEqual(p.status, "urgent")
        self.assertEqual(p.hours_left, 3.5)

    def test_missed(self):
        p = plan_appeal(date(2026, 10, 9), datetime(2026, 10, 8, 13, 0, tzinfo=NY), medicare_advantage=True)
        self.assertEqual(p.status, "missed")
        self.assertTrue(any("expedited" in s for s in p.if_missed))

    def test_late_notice_flag(self):
        p = plan_appeal(date(2026, 10, 9), datetime(2026, 10, 8, 8, 0, tzinfo=NY), notice_received=date(2026, 10, 8))
        self.assertTrue(p.notice_was_late)


if __name__ == "__main__":
    unittest.main()
