"""Unit tests for the deterministic cost engine. Run: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from engine.part_d_cost import DrugFill, annual_cost  # noqa: E402


class PartDCostTest(unittest.TestCase):
    def test_deductible_then_coinsurance_then_cap(self):
        brand = DrugFill("brand", 9.5, 60, True, 3, "coinsurance", 0.25, True)  # $570/month gross
        r = annual_cost("k", 20, 615, [brand], 2026)
        self.assertEqual(r.monthly_oop[0], 570.0)          # all deductible
        self.assertEqual(r.monthly_oop[1], 176.25)         # $45 deductible + 25% of $525
        self.assertEqual(r.drug_oop, 2100.0)               # 2026 cap
        self.assertEqual(r.annual_premium, 240.0)

    def test_copay_no_deductible(self):
        d = DrugFill("eliquis", 4.15, 60, True, 3, "copay", 47.0, False)
        self.assertEqual(annual_cost("k", 0, 0, [d]).drug_oop, 564.0)  # matches Plan Finder (Devoted 062)

    def test_copay_never_exceeds_drug_cost(self):
        d = DrugFill("cheap", 0.05, 30, True, 1, "copay", 10.0, False)  # $1.50 drug, $10 copay
        self.assertEqual(annual_cost("k", 0, 0, [d]).drug_oop, 18.0)

    def test_not_covered_is_reported_not_priced(self):
        r = annual_cost("k", 0, 0, [DrugFill("x", None, 30, False)])
        self.assertEqual(r.not_covered, ["x"])
        self.assertEqual(r.drug_oop, 0.0)

    def test_uncovered_drug_paid_in_full_outside_cap(self):
        covered = DrugFill("spec", 100, 30, True, 5, "coinsurance", 0.33, True)   # hits the cap
        uncovered = DrugFill("entresto", None, 60, False, uncovered_unit_cost=15.0)  # $900/month
        r = annual_cost("k", 0, 615, [covered, uncovered], 2026)
        self.assertEqual(r.covered_oop, 2100.0)
        self.assertEqual(r.uncovered_cost, 10800.0)
        self.assertEqual(r.drug_oop, 12900.0)

    def test_2027_cap(self):
        d = DrugFill("specialty", 100, 30, True, 5, "coinsurance", 0.33, True)
        self.assertEqual(annual_cost("k", 0, 700, [d], 2027).drug_oop, 2400.0)


if __name__ == "__main__":
    unittest.main()
