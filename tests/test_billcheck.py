import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from letters.billcheck import call_script, compare, money  # noqa: E402
from letters.checks import keyword_type  # noqa: E402

FIX = ROOT / "evals" / "fixtures" / "letters"


class BillCheck(unittest.TestCase):
    bill = {"provider_name": "Bayview Orthopedic Associates", "statement_date": "10/01/2026", "amount_due": "$115.00",
            "lines": [{"date": "08/12/2026", "description": "Office visit, established patient", "amount_due": "$40.00"},
                      {"date": "08/12/2026", "description": "X-ray, knee, 3 views", "amount_due": "$75.00"}]}
    eob = {"lines": [{"date": "08/12/2026", "description": "Specialist office visit", "you_owe": "$40.00"},
                     {"date": "08/12/2026", "description": "Diagnostic X-ray, knee", "you_owe": "$15.00"}]}

    def test_overbilled_line_found(self):
        r = compare(self.bill, self.eob)
        self.assertEqual(r["verdict"], "overbilled")
        self.assertEqual(r["over_by"], 60.0)
        self.assertEqual([x["status"] for x in r["lines"]], ["ok", "overbilled"])
        self.assertIn("$15.00", call_script(r, self.bill, "eob"))

    def test_matching_bill_is_ok(self):
        ok = dict(self.bill, amount_due="$55.00", lines=[dict(self.bill["lines"][0]), dict(self.bill["lines"][1], amount_due="$15")])
        r = compare(ok, self.eob)
        self.assertEqual(r["verdict"], "ok")
        self.assertIsNone(call_script(r, ok, "eob"))

    def test_line_missing_from_statement(self):
        r = compare({"lines": [{"date": "09/01/2026", "description": "Lab", "amount_due": 20}]}, self.eob)
        self.assertEqual(r["verdict"], "unmatched")

    def test_money_and_router(self):
        self.assertEqual(money("$1,234.50"), 1234.5)
        self.assertEqual(keyword_type((FIX / "bill.txt").read_text()), "bill")
        self.assertEqual(keyword_type((FIX / "eob.txt").read_text()), "eob")


if __name__ == "__main__":
    unittest.main()
