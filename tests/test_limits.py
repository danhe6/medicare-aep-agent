import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["RL_CHAT_MIN"] = "3"
os.environ["RL_SITE_CHAT_DAY"] = "5"

from fastapi import HTTPException  # noqa: E402

from api import limits  # noqa: E402


class FakeRequest:
    def __init__(self, ip, fwd=None):
        self.headers = {"x-forwarded-for": fwd} if fwd else {}
        self.client = type("C", (), {"host": ip})()


class LimitsTest(unittest.TestCase):
    def setUp(self):
        limits._hits.clear()
        limits._site.update(day="", chat=0)

    def test_per_visitor_burst(self):
        r = FakeRequest("1.1.1.1")
        for _ in range(3):
            limits.check(r, "chat")
        with self.assertRaises(HTTPException) as e:
            limits.check(r, "chat", "es")
        self.assertEqual(e.exception.status_code, 429)
        self.assertIn("Espere", e.exception.detail)

    def test_forwarded_ip_is_the_visitor(self):
        a, b = FakeRequest("10.0.0.2", "5.5.5.5"), FakeRequest("10.0.0.2", "6.6.6.6")
        for _ in range(3):
            limits.check(a, "chat")
        limits.check(b, "chat")  # same proxy, different visitor: not blocked

    def test_site_daily_cap(self):
        for i in range(5):
            limits.check(FakeRequest(f"9.9.9.{i}"), "chat")
        with self.assertRaises(HTTPException) as e:
            limits.check(FakeRequest("9.9.9.99"), "chat")
        self.assertIn("busy", e.exception.detail)


if __name__ == "__main__":
    unittest.main()
