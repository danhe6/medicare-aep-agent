import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["PUSH_DB"] = os.path.join(tempfile.mkdtemp(), "push.db")

from api import push  # noqa: E402


class Push(unittest.TestCase):
    def test_rfc8291_vector(self):
        """Encryption matches the worked example in RFC 8291, Appendix A."""
        from cryptography.hazmat.primitives.asymmetric import ec
        priv = ec.derive_private_key(int.from_bytes(push._b64d("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1())
        body = push.encrypt(b"When I grow up, I want to be a watermelon",
                            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
                            "BTBZMqHH6r4Tts7J_aSIgg", salt=push._b64d("DGv6ra1nlYgDCS1FRnbzlw"), private_key=priv)
        self.assertEqual(push._b64e(body), "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")

    def test_schedule(self):
        today = date(2026, 10, 9)
        self.assertEqual([str(s) for _, _, s in push.schedule("deadline", date(2026, 12, 6), today)], ["2026-11-29", "2026-12-04", "2026-12-06"])
        self.assertEqual([str(s) for _, _, s in push.schedule("nomnc", date(2026, 10, 10), today)], ["2026-10-09", "2026-10-10"])
        self.assertEqual([m for m, _, _ in push.schedule("enrollment", None, today)], ["aep_start", "aep_week", "aep_last", "oep_week"])
        self.assertEqual(push.schedule("deadline", date(2026, 10, 1), today), [])  # already past

    def test_messages_hold_no_personal_data(self):
        m = push.message("deadline", "2026-12-06", "en", date(2026, 12, 4))
        self.assertEqual(m["title"], "Appeal deadline in 2 days")
        self.assertIn("Dec 6, 2026", m["body"])
        self.assertIn("7 de dic", push.message("aep_week", "2026-12-07", "es")["body"])

    def test_save_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            push.save({"endpoint": "http://insecure", "keys": {}}, [{"kind": "enrollment"}])
        sub = {"endpoint": "https://push.example/x", "keys": {"p256dh": "a", "auth": "b"}}
        r = push.save(sub, [{"kind": "bogus"}, {"kind": "deadline", "date": "2099-01-01"}])
        self.assertEqual(r["dates"], [])  # unknown kind and far-future date both ignored
        self.assertEqual(push.save(sub, [{"kind": "enrollment"}])["id"], r["id"])  # same browser, same id
        push.delete(r["id"])


if __name__ == "__main__":
    unittest.main()
