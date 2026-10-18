import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from network import plan_news as pn  # noqa: E402

ARTICLES = [
    {"title": "Humana exit notices loom for 600,000 Medicare Advantage members", "url": "https://hfn.example/a",
     "content": "About 600,000 Humana members will get nonrenewal notices saying their plans won't be offered in 2027."},
    {"title": "Humana reports third-quarter earnings", "url": "https://news.example/b",
     "content": "Humana raised its 2027 outlook."},                      # no exit word: dropped
    {"title": "Aetna to exit some counties in 2027", "url": "https://news.example/c",
     "content": "Aetna will exit Medicare Advantage in 2027 in 100 counties."},   # other insurer: dropped
    {"title": "Humana exits markets", "url": "https://news.example/d", "content": "Humana exits markets in 2025."},  # wrong year
]


class PlanNews(unittest.TestCase):
    def setUp(self):
        pn._CACHE.clear()

    def test_only_articles_naming_insurer_exit_and_year(self):
        out = pn.plan_news("Humana Medical Plan, Inc.", 2027, state="FL", search=lambda q: ARTICLES)
        self.assertEqual(out["insurer"], "Humana")
        self.assertTrue(out["found_exit_news"])
        self.assertEqual([a["url"] for a in out["articles"]], ["https://hfn.example/a"])
        self.assertEqual(out["articles"][0]["site"], "hfn.example")

    def test_search_failure_is_soft(self):
        def boom(q):
            raise TimeoutError("slow")
        out = pn.plan_news("Devoted Health", 2027, search=boom)
        self.assertFalse(out["searched"])
        self.assertEqual(out["articles"], [])


if __name__ == "__main__":
    unittest.main()
