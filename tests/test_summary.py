import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import summary  # noqa: E402

BILL = {"verdict": "overbilled", "over_by": 60.0, "total_billed": 115.0, "total_you_owe": 55.0, "call_script": "Hi"}
LETTER = {"letter_type": "partd_denial", "title": "Your drug plan said no", "draft": "long text",
          "deadline": {"date": "2026-12-01", "date_text": "December 1, 2026", "days_left": 53}}


def session(*results):
    calls = [{"id": str(i), "type": "function", "function": {"name": n, "arguments": "{}"}} for i, (n, _) in enumerate(results)]
    msgs = [{"role": "system", "content": "s"}, {"role": "assistant", "content": "", "tool_calls": calls}]
    msgs += [{"role": "tool", "tool_call_id": str(i), "content": json.dumps(r)} for i, (_, r) in enumerate(results)]
    return msgs


class Summary(unittest.TestCase):
    def test_facts_keep_results_and_drop_drafts(self):
        f = summary.facts_from_session(session(("check_bill", BILL), ("read_medicare_letter", LETTER), ("find_drug", {"matches": []})))
        assert [x["check"] for x in f] == ["check_bill", "read_medicare_letter"]
        assert "call_script" not in f[0]["result"] and "draft" not in f[1]["result"]


    def test_numbers_must_come_from_facts(self):
        f = summary.facts_from_session(session(("check_bill", BILL), ("read_medicare_letter", LETTER)))
        assert summary.check_summary("The bill asks $60.00 more ($115 vs $55). Deadline 12/1/2026. Call 1-800-MEDICARE.", f) == []
        assert summary.check_summary("账单多收了60美元，截止日期是2026年12月1日。", f) == []
        assert summary.check_summary("That is about $720 a year.", f) == ["number not in facts: 720"]
        assert summary.check_summary("It will be approved.", f) == ["promises an outcome"]


    def test_nothing_to_summarize(self):
        assert summary.write([{"role": "system", "content": "s"}], llm=object()) == {"error": "nothing_yet"}


    def test_fallback_when_the_model_keeps_inventing_numbers(self):
        class Fake:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        m = type("M", (), {"content": "You will save $999."})
                        return type("R", (), {"choices": [type("C", (), {"message": m})]})
        out = summary.write(session(("check_bill", BILL)), lang="zh", llm=Fake)
        assert out["fallback"] and "$60.00" in out["text"] and "999" not in out["text"]


if __name__ == "__main__":
    unittest.main()
