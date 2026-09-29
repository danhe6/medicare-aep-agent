import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from engine import data  # noqa: E402


class NegotiatedPriceTest(unittest.TestCase):
    def setUp(self):
        import duckdb
        self.con = duckdb.connect()
        self.con.execute("""CREATE TABLE mfp AS SELECT * FROM (VALUES
            ('2026','ELIQUIS','000030893','00003089321',DATE '2026-01-01',DATE '2026-12-31',4.145072,'231'),
            ('2026','ELIQUIS','000030893','00003089321',DATE '2027-01-01',NULL,4.257193,'237.25'))
            t(ipay, drug, ndc9, ndc, start_date, end_date, unit_price, mfp_30day)""")

    def test_picks_price_in_effect(self):
        self.assertAlmostEqual(data.negotiated_unit_price(self.con, ["00003089321"], "2026-06-01")[0], 4.145072)
        self.assertAlmostEqual(data.negotiated_unit_price(self.con, ["00003089321"], "2027-01-01")[0], 4.257193)

    def test_not_negotiated(self):
        self.assertIsNone(data.negotiated_unit_price(self.con, ["99999999999"], "2027-01-01"))

    def test_release_without_table(self):
        import duckdb
        self.assertIsNone(data.negotiated_unit_price(duckdb.connect(), ["00003089321"], "2027-01-01"))


if __name__ == "__main__":
    unittest.main()
