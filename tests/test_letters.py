import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from letters.checks import check_draft, keyword_type  # noqa: E402
from letters.rules import plan  # noqa: E402

FIX = ROOT / "evals" / "fixtures" / "letters"
TODAY = date(2026, 10, 9)


class Router(unittest.TestCase):
    def test_sample_letters_route_by_title(self):
        for name in ("partd_denial", "ma_denial", "irmaa", "msn"):
            self.assertEqual(keyword_type((FIX / f"{name}.txt").read_text()), name)
        self.assertEqual(keyword_type("NOTICE OF MEDICARE NON-COVERAGE"), "nomnc")
        self.assertIsNone(keyword_type("Your pharmacy receipt"))


class Deadlines(unittest.TestCase):
    def test_partd_65_days_from_notice(self):
        p = plan("partd_denial", {"notice_date": "2026-10-02", "item": "Ozempic", "plan_name": "X"}, TODAY)
        self.assertEqual(p["deadline"]["date"], "2026-12-06")
        self.assertEqual(p["deadline"]["days_left"], 58)
        self.assertIn("Ozempic", p["doctor_request"])

    def test_ma_and_irmaa(self):
        self.assertEqual(plan("ma_denial", {"notice_date": "2026-09-30"}, TODAY)["deadline"]["date"], "2026-12-04")
        self.assertEqual(plan("irmaa", {"notice_date": "2026-09-22"}, TODAY)["deadline"]["date"], "2026-11-26")

    def test_msn_uses_printed_date_and_missing_date_asks(self):
        self.assertEqual(plan("msn", {"appeal_by": "2027-01-14"}, TODAY)["deadline"]["date"], "2027-01-14")
        p = plan("partd_denial", {}, TODAY, "es")
        self.assertIsNone(p["deadline"])
        self.assertIn("fecha", p["needs_date"])

    def test_missed(self):
        self.assertEqual(plan("partd_denial", {"notice_date": "2026-06-01"}, TODAY)["deadline"]["status"], "missed")


class DraftCheck(unittest.TestCase):
    facts = {"item": "Ozempic 1 mg/dose pen", "denial_reason": "try metformin first", "plan_name": "Sunshine"}

    def test_clean_paragraph_passes(self):
        self.assertEqual(check_draft("My doctor prescribed Ozempic 1 mg because [reason]. There were 3 [placeholder] options.",
                                     self.facts), ["number not in facts: 3"])
        self.assertEqual(check_draft("I ask you to reconsider. [What happened with metformin.]", self.facts), [])

    def test_invented_numbers_and_promises_fail(self):
        self.assertTrue(check_draft("My A1c was 9.2 last month.", self.facts))
        self.assertIn("promises an outcome", check_draft("This will be approved.", self.facts))
        self.assertTrue(check_draft("I previously attempted metformin but experienced side effects.", self.facts))
        self.assertEqual(check_draft("[Did you try metformin? What happened?] Please reconsider.", self.facts), [])


if __name__ == "__main__":
    unittest.main()
