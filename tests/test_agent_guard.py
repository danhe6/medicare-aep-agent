"""Code-enforced agent rules (found by evals/agent). No model calls.

    PYTHONPATH=src python -m pytest tests/test_agent_guard.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.agent import guard  # noqa: E402
from agent.tools import _full_state  # noqa: E402

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


def test_question_limit_offer_loop_and_income_routing():
    from agent.agent import style_problem
    two = "Which strength of Eliquis do you take? And what is the water pill called?"
    assert style_problem(two, [], "senior") and style_problem(two, [], "family") is None
    loop = [{"role": "assistant", "content": "Would you like me to check the quantity limit?"},
            {"role": "user", "content": "Yes, please check."}]
    assert style_problem("Would you like me to look up the quantity limit details?", loop)
    assert style_problem("The plan limits atorvastatin to 30 tablets per fill.", loop) is None
    es = [{"role": "user", "content": "Recibe como $1,300 al mes del seguro social. ¿Puede recibir ayuda para pagar sus medicinas?"}]
    assert "screen_extra_help" in style_problem("¿Qué medicinas toma?", es)
    done = es + [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "screen_extra_help"}}]}]
    assert style_problem("Es probable que califique.", done) is None
    assert style_problem("Could you confirm the exact plan ID from your card?", [])


def test_letter_rules_msn_not_a_bill_and_late_appeal():
    from datetime import date
    from letters.rules import plan
    msn = plan("msn", {"appeal_by": "2026-12-16"}, date(2026, 10, 13))
    assert "not a bill" in msn["title"] and "not a bill" in msn["steps"][0]
    late = plan("ma_denial", {"notice_date": "2026-08-04"}, date(2026, 10, 13))
    assert late["deadline"]["status"] == "missed" and "good cause" in late["steps"][0] and "true" in late["steps"][0]
    ok = plan("ma_denial", {"notice_date": "2026-10-01"}, date(2026, 10, 13))
    assert "late" not in ok


def test_grounding_spanish_thousands_and_examples():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals" / "agent"))
    from grounding import classify
    out = classify("Tiene unos $5,000 en ahorros.", [], ["tiene unos 5 mil en el banco"])
    assert out[0]["category"] == "exact"
    ex = classify("Example: estimated income $18,000 for this year", [], [])
    assert ex == []


def test_current_plan_pinned_to_notice_id():
    import json as _j
    from agent.agent import pin_current_plan
    msgs = [{"role": "assistant", "content": "", "tool_calls": [{"id": "a", "type": "function",
             "function": {"name": "read_medicare_letter", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "a", "content": _j.dumps({"letter_type": "anoc", "fields": {"plan_id": "H8069-055"}})}]
    args = {"current_plan": "Palmetto RX Saver (PDP)", "state": "Florida"}
    assert pin_current_plan("check_current_plan", args, msgs)["current_plan"] == "H8069-055"
    assert pin_current_plan("check_current_plan", {"current_plan": "H1019-057"}, msgs)["current_plan"] == "H1019-057"
    assert pin_current_plan("check_current_plan", args, [])["current_plan"] == "Palmetto RX Saver (PDP)"


def test_picked_names_must_be_used_exactly():
    from agent.agent import guard, picked_medicines
    msg = ("Compare plans in Miami-Dade, Florida. Medicines (exact names from the list): "
           "apixaban 2.5 MG Oral Tablet [Eliquis], 60 a month; metformin hydrochloride 500 MG Oral Tablet, 60 a month.")
    msgs = [{"role": "user", "content": msg}]
    assert picked_medicines(msgs) == {"apixaban 2.5 MG Oral Tablet [Eliquis]", "metformin hydrochloride 500 MG Oral Tablet"}
    ok = {"state": "Florida", "county": "Miami-Dade", "drugs": [
        {"rxnorm_name": "apixaban 2.5 MG Oral Tablet [Eliquis]", "qty_per_30d": 60},
        {"rxnorm_name": "metformin hydrochloride 500 MG Oral Tablet", "qty_per_30d": 60}]}
    assert guard("compare_plans", ok, msgs) is None
    swapped = {**ok, "drugs": [{"rxnorm_name": "apixaban 2.5 MG Oral Tablet", "qty_per_30d": 60},
                               {"rxnorm_name": "metformin hydrochloride 500 MG Oral Tablet", "qty_per_30d": 60}]}
    assert "[Eliquis]" in guard("compare_plans", swapped, msgs)


def test_made_up_number_is_sent_back_for_rewrite():
    # h14 (10/18): "the standard amount is around $174.70" with no tool call - a remembered, out-of-date premium.
    from agent.agent import style_problem, ungrounded_numbers
    msgs = [{"role": "user", "content": "How much is my Part B premium going to be next year?"}]
    draft = "The standard amount is projected to be around $174.70 per month."
    assert ungrounded_numbers(draft, msgs) == ["$174.70"]
    assert "from memory" in style_problem(draft, msgs)
    msgs += [{"role": "tool", "content": '{"part_b_monthly_premium": 202.9}'}]
    assert ungrounded_numbers("Part B is $202.90 a month.", msgs) == []


def test_no_extra_questions_once_county_and_medicine_known():
    # h01 (10/18): county + "atorvastatin 20 mg" given, agent asked about other medicines and re-confirmed Medicaid.
    from agent.agent import style_problem
    msgs = [{"role": "user", "content": "She takes atorvastatin 20 mg once a day and lives in Miami-Dade County."}]
    assert "compare_plans now" in style_problem("Does she take any other prescription medicines regularly?", msgs)
    assert style_problem("Also, to confirm, she does not have Medicaid, correct?", msgs)


def test_promise_without_tool_call_is_sent_back():
    # h06 (10/18): "I'll start by looking up the plans..." and no tool call.
    from agent.agent import style_problem
    msgs = [{"role": "user", "content": "My aunt takes losartan. Show her the best plans."}]
    assert "call the tools" in style_problem("I'll start by looking up the plans for Miami-Dade County.", msgs)
    msgs += [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "find_drug"}}]},
             {"role": "tool", "content": "{}"}]
    assert style_problem("I'll check the network next.", msgs) is None


def test_letter_deadline_is_always_stated():
    # m08 (10/18): the reply after reading a Part D denial gave steps but not the Dec 2 deadline the code computed.
    import json
    from agent.agent import add_required_notes, _mentions_date
    dl = {"date": "2026-12-02", "date_text": "December 2, 2026", "days_left": 45, "status": "on_time"}
    msgs = [{"role": "user", "content": "my drug plan said no"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "t1", "function": {"name": "read_medicare_letter"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": json.dumps({"letter_type": "partd_denial", "deadline": dl})}]
    out = add_required_notes("Ask your doctor for a supporting statement.", msgs, [])
    assert "December 2, 2026" in out and "45 days" in out
    assert add_required_notes("Send it by Dec 2.", msgs, []) == "Send it by Dec 2."
    assert _mentions_date("antes del 2 de diciembre", "2026-12-02", None)
    assert not _mentions_date("within 7 days", "2026-12-02", "December 2, 2026")


def test_offer_again_after_yes_is_sent_back():
    # m08 (10/18): "Yes please." -> "Sure, I'll prepare the letter. Does that sound good?"
    from agent.agent import style_problem
    msgs = [{"role": "assistant", "content": "Would you like me to prepare that letter for you?"},
            {"role": "user", "content": "Yes please."}]
    assert "already said yes" in style_problem("Sure, I'll prepare the appeal letter for you. Does that sound good?", msgs)


def test_dose_from_memory_is_sent_back():
    # m02 (10/18): "Common strengths are 20 mg or 40 mg" with no tool listing 40 mg.
    from agent.agent import ungrounded_numbers
    msgs = [{"role": "user", "content": "I take a water pill, furosemide."}]
    assert "40 mg" in ungrounded_numbers("What strength? Common strengths are 20 mg or 40 mg.", msgs)
    msgs.append({"role": "tool", "content": '{"all_strengths": [{"rxnorm_name": "furosemide 20 MG Oral Tablet"}, {"rxnorm_name": "furosemide 40 MG Oral Tablet"}]}'})
    assert ungrounded_numbers("What strength? It comes in 20 mg or 40 mg.", msgs) == []


def test_name_from_all_strengths_passes_guard():
    # k02 (10/18): the generic eye drop was only in all_strengths, not in matches.
    import json
    from agent.agent import guard
    name = "latanoprost 0.05 MG/ML Ophthalmic Solution"
    msgs = [{"role": "user", "content": "latanoprost drops"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "f1", "type": "function",
                                                                "function": {"name": "find_drug", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "f1", "content": json.dumps(
                {"results": [{"query": "latanoprost", "matches": [], "all_strengths": [{"rxnorm_name": name}]}]})}]
    assert guard("compare_plans", {"state": "FL", "county": "Broward",
                                   "drugs": [{"rxnorm_name": name, "qty_per_30d": 2.5}]}, msgs) is None


def test_no_question_about_dose_form_when_strength_known():
    # k06 (10/18): asked tablet/capsule/disintegrating for "omeprazole 20 mg" three times; the person said "I don't know".
    from agent.agent import style_problem
    msgs = [{"role": "user", "content": "I take lisinopril 10 mg and omeprazole 20 mg, once a day each."},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "f", "function": {"name": "find_drug"}}]},
            {"role": "tool", "tool_call_id": "f", "content": "{}"}]
    draft = "Which form of omeprazole do you take: tablet, capsule, or disintegrating tablet?"
    assert "form you priced" in style_problem(draft, msgs)
