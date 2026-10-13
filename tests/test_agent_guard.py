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


def test_anoc_plan_must_be_checked_before_comparing():
    from agent.agent import guard
    msgs = convo("Is something changing for me next year?")
    msgs += [{"role": "assistant", "content": "", "tool_calls": [
                 {"id": "t9", "type": "function", "function": {"name": "read_medicare_letter", "arguments": "{}"}}]},
             {"role": "tool", "tool_call_id": "t9",
              "content": json.dumps({"letter_type": "anoc", "fields": {"plan_id": "H8966-048"}})},
             {"role": "user", "content": "Miami-Dade, I take Eliquis"}]
    err = guard("compare_plans", plans(ELIQUIS), msgs)
    assert err and "H8966-048" in err


def test_polish_and_style_problems():
    from agent.agent import polish, style_problem
    assert polish("Plan H1019-001-000 and S5921-356-000") == "Plan H1019-001 and S5921-356"
    assert style_problem("| Plan | Cost |\n|---|---|\n| A | $0 |")
    assert style_problem("You take Eliquis in Miami-Dade. Is that correct?")
    assert style_problem("The best plan is CareOne Plus.") is None


def test_reconfirm_variants_and_dont_know_loop():
    from agent.agent import style_problem
    assert style_problem("You take metformin 500 mg twice a day. Does that sound right?")
    convo = [{"role": "user", "content": "I take lisinopril."},
             {"role": "assistant", "content": "Do you have Medicaid?"},
             {"role": "user", "content": "I don't know."}]
    assert style_problem("Are you enrolled in Medicaid?", convo)
    assert style_problem("The best plan is Wellcare Value Script.", convo) is None
    first = [{"role": "user", "content": "I don't know where to start."}]
    assert style_problem("Which county do you live in?", first) is None  # nothing asked before


def test_required_notes_quantity_and_medicare_number():
    from agent.agent import add_required_notes
    lantus = [{"rxnorm_name": "insulin glargine 100 UNT/ML Injectable Solution [Lantus]", "qty_per_30d": 6},
              {"rxnorm_name": "metformin hydrochloride 1000 MG Oral Tablet", "qty_per_30d": 60}]
    out = add_required_notes("CareOne Plus is cheapest.", [{"role": "user", "content": "Lantus 20 units"}], lantus)
    assert "Lantus at 6 mL" in out and "metformin" not in out.split("cheapest.")[1]
    assert add_required_notes("I used 6 mL of Lantus a month.", [], lantus) == "I used 6 mL of Lantus a month."
    mbi = [{"role": "user", "content": "My Medicare number is 1EG4-TE5-MK73, please save it."}]
    assert "don't save Medicare numbers" in add_required_notes("Best plan: X.", mbi, [])
    assert add_required_notes("I won’t store your number.", mbi, []) == "I won’t store your number."
    assert "No guardo" in add_required_notes("Plan X.", mbi, [], lang="es")


def test_grounding_money_not_thousands_before_a_word():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals" / "agent"))
    from grounding import claims
    vals = {c["text"]: c["value"] for c in claims("a $75 knee X-ray, income $75k, and $20 K")}
    assert vals["$75"] == 75 and vals["$75k"] == 75000


def test_no_asking_for_location_already_given(monkeypatch=None):
    from unittest import mock
    import agent.agent as A
    with mock.patch.object(A, "_known_counties", lambda: frozenset({"broward", "miami-dade"})):
        _location_checks(A.style_problem)


def _location_checks(style_problem):
    broward = [{"role": "user", "content": "I live in Broward and take atorvastatin 20 mg once a day."}]
    assert style_problem("Which city in Broward County do you live in?", broward)
    assert style_problem("Are you in Broward County, Florida? (Yes or No)", broward)
    assert style_problem("The best plan is Wellcare Value Script.", broward) is None
    nowhere = [{"role": "user", "content": "I take atorvastatin 20 mg once a day."}]
    assert style_problem("Which county do you live in?", nowhere) is None
    assert style_problem("Once a day is about 30 tablets a month, is that right for both of them?")
    assert style_problem("Could you tell me which city or area you live in?", broward)
    # a doctor's city is not the person's location
    assert style_problem("I need the city where she sees patients (for example, Miami). Which city is it?", broward) is None


def test_required_note_when_asked_to_promise():
    from agent.agent import add_required_notes
    ask = [{"role": "user", "content": "Promise me I'll pay $0 next year."}]
    assert "not a promise" in add_required_notes("Leon MediExtra shows about $0.", ask, [])
    assert add_required_notes("This is an estimate.", ask, []) == "This is an estimate."
    assert "no una promesa" in add_required_notes("Plan X.", [{"role": "user", "content": "¿Me lo garantiza?"}], [], lang="es")


def test_flatten_tables():
    from agent.agent import flatten_tables
    t = "Plans:\n| Plan | Cost |\n|---|---|\n| Wellcare | $0 |\n| Humana | $0 |\nDone."
    assert flatten_tables(t) == "Plans:\n- Wellcare - $0\n- Humana - $0\nDone."
    assert flatten_tables("No table here.") == "No table here."
