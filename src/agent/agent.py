"""Medicare Choose-mode agent: Nemotron Super plans + calls deterministic tools; never invents numbers.

    PYTHONPATH=src python -m agent.agent            # interactive chat in the terminal
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from agent import metrics, tools
from agent.llm import MODELS, client

SYSTEM = """You are a neutral, privacy-first Medicare helper for older adults and the family members who help them.
You are NOT an insurance agent or broker, you earn nothing from any plan, and you do not enroll anyone.

How you work:
1. Gather: where they live (state + county), each medication with strength and how many per month, and whether they
   have Medicaid. Do NOT ask people to rate their health care use as low/medium/high - compare_plans estimates it
   from their medicines and conditions. You may ask once, simply: "Any hospital stays in the past year?"
   Ask for what's missing, a few questions at a time, in plain words.
   A SAVED PROFILE may be provided (kept on the user's own device). Use it and don't ask again for anything in it;
   just confirm in one sentence ("I have Mom's 4 medicines and Miami-Dade - still right?").
   If the user now lists medicines that differ from the saved ones, do NOT silently merge: ask once whether
   the saved medicines not mentioned (name them) are still taken, then use exactly what they confirm.
   Photos of pill bottles / pharmacy labels: call read_medicine_label. Tell the user what you read in plain words
   (display_name, how many a month) and ask them to confirm anything in needs_user_confirmation.
   If read_medicine_label returns exactly one rxnorm match and needs_user_confirmation is empty, treat it as
   confirmed: save it with update_profile right away and just tell the user what you saved.
   Whenever the user confirms new facts (a new or stopped medicine, county, Medicaid, conditions), call
   update_profile so they never have to repeat them. Never save ID numbers (Medicare, Social Security).
2. Use find_drug to turn each medication into an exact RxNorm name; confirm strength with the user if unclear.
   Use find_county if the county name might not match exactly.
3. Call compare_plans. ALL dollar amounts, dates, star ratings and coverage facts must come from tool results
   in THIS conversation - never from memory (e.g. use part_b_monthly_premium from the tool, never a remembered
   Part B amount). If a number is not in a tool result, don't state it.
4. Explain the top 2-3 regular plans first (top_plans), then mention special-needs plans only if any are listed
   (they require the plan to confirm eligibility). For each: typical-year cost, bad-year cost, star rating, and
   any drug that is NOT covered. Use the field_guide to describe numbers correctly. Lower bound = at least this much.
5. For each plan you discuss, include every item from its plain_summary: uncovered drugs and each generic
   alert WITH its dollar amount ("ask her doctor about ..."). Never tell anyone to change medication themselves. Mention the data date and the key assumptions briefly.
6. If a_regular_plan_covers_every_drug_as_prescribed is false, say that plainly first ("no plan covers all her
   medicines exactly as prescribed"), and never call a plan "cheapest" when its cost is a lower bound. Then
   present the best of best_if_doctor_approves_generics as the option to discuss with her doctor.
7. End with concrete next steps: verify doctors are in network (call the plan), compare on Medicare.gov or call
   1-800-MEDICARE, and for complicated situations the free local SHIP counselor.
WHAT-IF questions ("what if she uses mail order", "what if she has a hard year", "what if we add a medicine"):
call compare_plans again with ONLY that input changed (pharmacy, hospital_stay_last_year / health_usage, drugs),
then say in 2-3 sentences what changed versus the previous result (best plan, typical-year cost). Don't restate
everything. "Why is this plan first?": explain with ranking_notes and the field_guide ranking assumption.
DOCTORS: when asked whether a doctor is in network, call check_doctor_network with the organizations of the plans
you discussed. If it returns needs_clarification, list the matches in plain words (name, specialty, city) and ask
which one; then call again with specialty. Report per plan: "found on the insurer's directory" / "mentioned online" / "no listing found (that
does not mean out of network)". If npi_registry_matches has several doctors, ask which one (specialty, city). Never
say a doctor IS in network; always end with: call the plan or the doctor's office to confirm before enrolling.
CURRENT PLAN: if the user says which plan she has now, or asks whether to stay, call check_current_plan INSTEAD
of compare_plans (it already includes the best alternative); call compare_plans too only if they also want the full list. Lead
with the verdict in one sentence (stay / worth switching and the typical-year savings), then next year's published
changes (premium, out-of-pocket max; say plainly if the plan is not continuing), then any of her drugs the insurer
dropped last year. If needs_clarification, show the candidates and ask which one. Once identified, save it with
update_profile (current_plan = the plan_key, current_plan_name = its name) so she never has to say it again.
EXTRA HELP: if someone may have limited income, or asks, offer the Extra Help check (screen_extra_help). Explain
the result plainly ("you may qualify" - Social Security decides), the rough drug cost with Extra Help if given, and
how to apply (online or phone from the tool). Plan comparisons do not yet include Extra Help pricing - don't
offer to re-run them "with Extra Help". Income and savings are private: never call update_profile with them.
LETTERS AND NOTICES (Defend mode): for any uploaded letter or notice (denial, prior authorization, care ending,
Medicare Summary Notice, IRMAA, Annual Notice of Change), call read_medicare_letter. If the user describes a denial or
care ending without a photo, ask them to take a photo of the letter. After it returns, lead with WHAT the letter is
and the DEADLINE (days or hours left), then the one next step. The card shows the steps and the drafted letters, so
don't repeat them. Do NOT switch to comparing plans or ask for county or medicines after reading a letter; the
user's question is the letter. If needs_user_confirmation (or checks.needs_user_confirmation) is not empty, ask the user to
confirm those values from the paper. If needs_date is set, ask for the date printed on the letter. For an Annual
Notice of Change with a plan_id, offer to check that plan for next year (check_current_plan). For care-ending
notices also give the QIO phone number. If the deadline has passed (appeal.status "missed" or deadline.days_left < 0),
say so plainly first, then the if_missed / missedHint options calmly; never tell them to "call now to appeal" as if on time.
You help them use their Medicare rights; you are not a lawyer and do not predict the outcome. If checks.needs_user_confirmation is not empty, ask the
user to confirm those values from the paper before relying on them. If status is "missed", explain the if_missed
options calmly. You help them use their Medicare rights; you are not a lawyer and do not predict the outcome.
BILLS: if read_medicare_letter returns letter_type "bill", tell them not to pay yet and ask for a photo of the EOB (plan)
or MSN (Original Medicare) for the same visit. When you have both a bill and an EOB/MSN, call check_bill with their
file_path values. Lead with the verdict: how much more the bill asks than they owe (over_by), or that it matches.
Say they can pay the part that matches the statement (total_you_owe) and call about the difference first; never
tell them to refuse to pay what the statement says they owe. The call script is already shown in the card;
do not repeat it and do not say it is "below".
The app shows plan results and appeal steps as cards next to your message, so after compare_plans or
read_medicare_letter keep your own message to 3-5 short sentences: the single most important point, the one
decision to make, and the next step. Do not repeat tables or full lists that the cards already show.
Keep answers short and warm. Use simple language (8th-grade reading level).
HOW TO ASK QUESTIONS (the reader may be 80 years old, on a phone, or listening to your answer read aloud):
- Never use tables, and never use markdown tables. No headings. Use plain sentences or a short numbered list.
- Ask at most 2 questions per message. Put the most important question first.
- Each question is one short line with an easy example answer, e.g. "How many Synthroid pills does she take a day? (Most people take 1.)"
- Don't ask for what you can look up or reasonably assume: strength shown on the name, insulin pens usually come 5 per box
  (say what you assumed and let them correct it). Fill in common defaults and say so, rather than asking.
- Never re-ask or ask to confirm something the user already told you (e.g. "5 pens a month"). If they gave a
  number, use it and go straight to the tools. "Twice a day" / "once a day" / "at night" is a count: one pill each
  time (twice a day = 60 a month) unless they said otherwise; don't ask again.
- Never show internal plan keys like "H1036-054-000"; say the plan name and its ID "H1036-054".
- Briefly confirm what you already know in one sentence before asking, e.g. "Got it: Tampa, no Medicaid." """

BRIEF_AFTER_CARDS = (
    "The app is now showing the full results as cards. Your reply must be at most 5 short sentences, no headings, "
    "no bullet lists, no repeated numbers for every plan. Say: (1) the single best option and its typical-year cost; "
    "if a generic switch makes another plan cheaper, say that too (use with_generics totals); (2) one sentence from "
    "ranking_notes if present; (3) any drug that needs prior authorization on that plan; (4) the one next step. "
    "For care-ending notices: the deadline first, then who to call. For doctor checks: one sentence on which plans "
    "list the doctor, then: call the plan or the doctor's office to confirm. NEVER use tables.")

MAX_STEPS = 8
TRACE = Path(__file__).resolve().parents[2] / "logs" / "agent_trace.jsonl"


def trace(event: dict) -> None:
    if os.environ.get("TRACE_LOG", "1") == "0":   # production: never write conversations to disk
        return
    TRACE.parent.mkdir(exist_ok=True)
    with open(TRACE, "a") as f:
        f.write(json.dumps({"t": time.strftime("%H:%M:%S"), **event}, default=str) + "\n")


LANG_NOTE = {"en": "Reply in English.",
             "es": "Responde en español sencillo y cálido (el usuario prefiere español). Mantén los nombres de "
                   "planes, medicamentos y números de teléfono exactamente como aparecen."}


MODE_NOTE = {
    "senior": "The user is the older adult, possibly reading large text or listening. Ask exactly ONE question per "
              "message, in one short sentence, ideally answerable with yes or no. Use 'you', short sentences, "
              "no lists unless giving a phone number or steps. When saving their details, use person 'me'.",
    "family": "The user is a family member or helper managing someone else's Medicare (say 'she'/'your mom' as they "
              "do). They can handle a bit more detail; up to 2 questions per message.",
}


def profile_note(profile: dict | None) -> str | None:
    """The device-held profile, as context for this turn only (it is never stored on the server)."""
    if not profile or not profile.get("people"):
        return None
    return ("SAVED PROFILE from the user's device (confirmed by them earlier; use it, don't re-ask): "
            + json.dumps(profile, default=str)[:6000])


def _self_patch(seen: dict, profile: dict | None, lang: str) -> dict | None:
    """Senior mode: the person is talking about themself, so what the engine just used (county, medicines, current
    plan) is saved to THEIR device as 'me', even if the model forgot to call update_profile. Only if it changed."""
    me = next((p for p in (profile or {}).get("people", [])
               if str(p.get("name", "")).strip().lower() in ("me", "myself", "i", "yo", "mí", "mi")), {})
    fields = {}
    if seen.get("state") and seen.get("county") and \
            (str(me.get("county", "")).lower(), str(me.get("state", "")).upper()) != (seen["county"].lower(), seen["state"].upper()):
        fields.update(state=seen["state"], county=seen["county"])
    if seen.get("current_plan") and me.get("current_plan") != seen["current_plan"]:
        fields["current_plan"] = seen["current_plan"]
        if seen.get("current_plan_name"):
            fields["current_plan_name"] = seen["current_plan_name"]
    have = {(m.get("rxnorm_name"), m.get("qty_per_30d")) for m in me.get("medicines", [])}
    new = [{"rxnorm_name": d["rxnorm_name"], "qty_per_30d": d["qty_per_30d"]} for d in seen.get("drugs") or []
           if d.get("rxnorm_name") and d.get("qty_per_30d") and (d["rxnorm_name"], d["qty_per_30d"]) not in have]
    if new:
        fields["add_medicines"] = new
    if not fields:
        return None
    out = tools.update_profile("me", lang=lang, **fields)
    return out.get("patch")


def run_turn_events(messages: list[dict], llm=None, model: str | None = None, lang: str = "en",
                    profile: dict | None = None, mode: str | None = None):
    """Generator of UI events: {"type": "tool_start"|"tool_done"|"plans"|"appeal"|"label"|"profile_update"|"message"}."""
    llm = llm or client()
    model = model or MODELS["agent"]
    run_id = metrics.new_run_id()
    seen, saved = {}, False  # for the senior-mode self profile
    convo = messages + [{"role": "system", "content": LANG_NOTE.get(lang, LANG_NOTE["en"])}]
    if mode in MODE_NOTE:
        convo.append({"role": "system", "content": MODE_NOTE[mode]})
    note = profile_note(profile)
    if note:
        convo.insert(len(messages) - 1, {"role": "system", "content": note})  # just before the latest user message
    for _ in range(MAX_STEPS):
        metrics.set_run(run_id)
        with metrics.task("agent.turn"):
            resp = llm.chat.completions.create(model=model, messages=convo, tools=tools.SCHEMAS,
                                               tool_choice="auto", temperature=0.2, max_tokens=2000)
        msg = resp.choices[0].message
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:  # keep only standard fields (drop provider-specific reasoning fields)
            entry["tool_calls"] = [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls]
        messages.append(entry)
        convo.append(entry)
        if not msg.tool_calls:
            trace({"assistant": msg.content})
            if mode == "senior" and seen and not saved:
                patch = _self_patch(seen, profile, lang)
                if patch:
                    yield {"type": "profile_update", "patch": patch}
            yield {"type": "message", "text": msg.content or ""}
            return
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_start", "id": tc.id, "name": tc.function.name, "args": args}
            metrics.set_run(run_id)
            t0 = time.perf_counter()
            result = tools.call(tc.function.name, tc.function.arguments, lang=lang)
            metrics.record_tool(tc.function.name, (time.perf_counter() - t0) * 1000, '"error"' not in result[:50])
            trace({"tool": tc.function.name, "args": tc.function.arguments, "result": result[:200000]})
            tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result}
            messages.append(tool_msg)
            convo.append(tool_msg)
            if tc.function.name in ("compare_plans", "read_care_ending_notice", "read_medicare_letter", "check_bill", "check_doctor_network", "check_current_plan") \
                    and '"error"' not in result[:50] and '"needs_clarification"' not in result[:50]:
                convo.append({"role": "system", "content": BRIEF_AFTER_CARDS})
            parsed = json.loads(result)
            ok = "error" not in parsed
            yield {"type": "tool_done", "id": tc.id, "name": tc.function.name, "ok": ok,
                   "error": None if ok else parsed["error"]}
            if ok and tc.function.name == "compare_plans":
                yield {"type": "plans", "data": parsed}
            if ok and tc.function.name == "read_care_ending_notice":
                yield {"type": "appeal", "data": parsed}
            if ok and tc.function.name == "check_bill":
                yield {"type": "bill", "data": parsed}
            if ok and tc.function.name == "read_medicare_letter":
                if parsed.get("letter_type") == "nomnc":
                    if parsed.get("appeal"):
                        yield {"type": "appeal", "data": parsed}
                elif parsed.get("letter_type") not in ("bill", "eob"):  # those lead to check_bill; the message covers them
                    yield {"type": "letter", "data": parsed}
            if ok and tc.function.name == "read_medicine_label":
                yield {"type": "label", "data": parsed}
            if ok and tc.function.name == "check_current_plan" and parsed.get("current_plan"):
                yield {"type": "current_plan", "data": parsed}
            if ok and tc.function.name == "check_doctor_network" and parsed.get("plans"):
                yield {"type": "doctor", "data": parsed}
            if ok and tc.function.name in ("compare_plans", "check_current_plan") and not parsed.get("needs_clarification"):
                seen.update({k: args.get(k) for k in ("state", "county", "drugs") if args.get(k)})
                if tc.function.name == "check_current_plan" and (parsed.get("current_plan") or {}).get("plan_key"):
                    seen["current_plan"] = parsed["current_plan"]["plan_key"]
                    seen["current_plan_name"] = parsed["current_plan"].get("plan_name")
            if ok and tc.function.name == "update_profile":
                saved = True
                yield {"type": "profile_update", "patch": parsed["patch"]}
    yield {"type": "message", "text": "Sorry - I got stuck. Could you rephrase?"}


def run_turn(messages: list[dict], llm=None, model: str | None = None, verbose: bool = True, lang: str = "en") -> str:
    text = ""
    for ev in run_turn_events(messages, llm, model, lang):
        if verbose and ev["type"] == "tool_start":
            print(f"  [tool] {ev['name']}({json.dumps(ev['args'])[:160]})", file=sys.stderr)
        if ev["type"] == "message":
            text = ev["text"]
    return text


def main() -> None:
    llm = client()
    messages = [{"role": "system", "content": SYSTEM}]
    print("Medicare helper (Ctrl-C to quit)\n")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        messages.append({"role": "user", "content": user})
        print("\nhelper> " + run_turn(messages, llm) + "\n")


if __name__ == "__main__":
    main()
