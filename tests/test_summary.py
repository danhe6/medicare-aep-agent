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


    def test_bad_year_ceiling_is_not_the_cost(self):
        # Live site 10/26: two $0 plans with a $500 bad-year ceiling were summarized as "costo estimado de $500 al año".
        plans = {"top_plans": [{"plan_name": "CareOne Plus (HMO)", "total": 0.0, "bad_year_total": 500.0, "moop": 500.0,
                                "annual_premium": 0.0, "drug_oop": 0.0, "expected_total": 120.0, "not_covered": []}],
                 "field_guide": {"total": "typical year"}}
        f = summary.facts_from_session(session(("compare_plans", plans)))
        p = f[0]["result"]["top_plans"][0]
        assert p["typical_year_cost"] == 0.0 and p["most_paid_in_a_very_bad_health_year"] == 500.0
        assert "total" not in p and "expected_total" not in p and "field_guide" not in f[0]["result"]
        bad = summary.check_summary("CareOne Plus (HMO), con costo estimado de $500 al año.", f)
        assert len(bad) == 1 and "typical-year cost ($0)" in bad[0] and "not the expected cost" in bad[0]
        assert summary.check_summary("CareOne Plus (HMO): $0 en un año típico; como máximo $500 en un año muy malo.", f) == []
        miss = summary.check_plan_cost("Best plan is CareOne Plus.", f)  # cost left out entirely
        assert len(miss) == 1 and "not the expected cost" not in miss[0]
        t = summary._template(f, "es")
        assert "$0 en un año típico" in t and "como máximo $500" in t


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
