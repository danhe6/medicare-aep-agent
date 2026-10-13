"""Code-enforced agent rules (found by evals/agent). No model calls.

    PYTHONPATH=src python -m pytest tests/test_agent_guard.py -q
"""
import json

from agent.agent import guard
from agent.tools import _full_state

ELIQUIS = "apixaban 5 MG Oral Tablet [Eliquis]"


def convo(user: str, lookups=(ELIQUIS,)):
    msgs = [{"role": "system", "content": "x"}, {"role": "user", "content": user}]
    if lookups:
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": "t1", "type": "function", "function": {"name": "find_drug", "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": "t1",
                     "content": json.dumps({"matches": [{"rxnorm_name": n} for n in lookups]})})
    return msgs


def plans(*names):
    return {"state": "Florida", "county": "Miami-Dade", "drugs": [{"rxnorm_name": n, "qty_per_30d": 60} for n in names]}


def test_drug_names_must_come_from_find_drug():
    msgs = convo("Mom takes Eliquis and metformin in Miami-Dade")
    assert guard("compare_plans", plans(ELIQUIS), msgs) is None
    err = guard("compare_plans", plans(ELIQUIS, "metformin 500 MG Oral Tablet"), msgs)
    assert err and "metformin 500 MG Oral Tablet" in err


def test_saved_profile_medicines_count_as_looked_up():
    msgs = convo("Compare plans again", lookups=())
    profile = {"people": [{"name": "Mom", "medicines": [{"rxnorm_name": ELIQUIS, "qty_per_30d": 60}]}]}
    assert guard("compare_plans", plans(ELIQUIS), msgs, profile) is None


def test_named_current_plan_needs_check_current_plan_first():
    msgs = convo("I'm in plan H1019-006. Should I stay on my plan next year?")
    assert guard("compare_plans", plans(ELIQUIS), msgs)
    assert guard("check_current_plan", {**plans(ELIQUIS), "current_plan": "H1019-006"}, msgs) is None
    msgs += [{"role": "assistant", "content": "", "tool_calls": [
                 {"id": "t2", "type": "function", "function": {"name": "check_current_plan", "arguments": "{}"}}]},
             {"role": "tool", "tool_call_id": "t2", "content": "{}"}]
    assert guard("compare_plans", plans(ELIQUIS), msgs) is None


def test_plain_comparison_is_not_blocked():
    assert guard("compare_plans", plans(ELIQUIS), convo("Which plans are cheapest for Mom?")) is None


def test_state_abbreviations():
    assert _full_state("FL") == "Florida"
    assert _full_state("fl") == "Florida"
    assert _full_state("DC") == "District of Columbia"
    assert _full_state("Florida") == "Florida"
