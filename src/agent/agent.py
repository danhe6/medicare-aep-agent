"""Medicare Choose-mode agent: Nemotron Super plans + calls deterministic tools; never invents numbers.

    PYTHONPATH=src python -m agent.agent            # interactive chat in the terminal
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from agent import tools
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
CARE ENDING (Defend mode): if the user says nursing home / rehab / home health care is being stopped, or shares a
Notice of Medicare Non-Coverage, call read_care_ending_notice. Then lead with the DEADLINE and hours left, then
the QIO phone number and call script, then the checklist. If checks.needs_user_confirmation is not empty, ask the
user to confirm those values from the paper before relying on them. If status is "missed", explain the if_missed
options calmly. You help them use their Medicare rights; you are not a lawyer and do not predict the outcome.
The app shows plan results and appeal steps as cards next to your message, so after compare_plans or
read_care_ending_notice keep your own message to 3-5 short sentences: the single most important point, the one
decision to make, and the next step. Do not repeat tables or full lists that the cards already show.
Keep answers short and warm. Use simple language (8th-grade reading level).
HOW TO ASK QUESTIONS (the reader may be 80 years old, on a phone, or listening to your answer read aloud):
- Never use tables, and never use markdown tables. No headings. Use plain sentences or a short numbered list.
- Ask at most 2 questions per message. Put the most important question first.
- Each question is one short line with an easy example answer, e.g. "How many Synthroid pills does she take a day? (Most people take 1.)"
- Don't ask for what you can look up or reasonably assume: strength shown on the name, insulin pens usually come 5 per box
  (say what you assumed and let them correct it). Fill in common defaults and say so, rather than asking.
- Never re-ask or ask to confirm something the user already told you (e.g. "5 pens a month"). If they gave a
  number, use it and go straight to the tools.
- Briefly confirm what you already know in one sentence before asking, e.g. "Got it: Tampa, no Medicaid." """

BRIEF_AFTER_CARDS = (
    "The app is now showing the full results as cards. Your reply must be at most 5 short sentences, no headings, "
    "no bullet lists, no repeated numbers for every plan. Say: (1) the single best option and its typical-year cost; "
    "if a generic switch makes another plan cheaper, say that too (use with_generics totals); (2) one sentence from "
    "ranking_notes if present; (3) any drug that needs prior authorization on that plan; (4) the one next step. "
    "For care-ending notices: the deadline first, then who to call.")

MAX_STEPS = 8
TRACE = Path(__file__).resolve().parents[2] / "logs" / "agent_trace.jsonl"


def trace(event: dict) -> None:
    TRACE.parent.mkdir(exist_ok=True)
    with open(TRACE, "a") as f:
        f.write(json.dumps({"t": time.strftime("%H:%M:%S"), **event}, default=str) + "\n")


LANG_NOTE = {"en": "Reply in English.",
             "es": "Responde en español sencillo y cálido (el usuario prefiere español). Mantén los nombres de "
                   "planes, medicamentos y números de teléfono exactamente como aparecen."}


MODE_NOTE = {
    "senior": "The user is the older adult, possibly reading large text or listening. Ask exactly ONE question per "
              "message, in one short sentence, ideally answerable with yes or no. Use 'you', short sentences, "
              "no lists unless giving a phone number or steps.",
    "family": "The user is a family member or helper managing someone else's Medicare (say 'she'/'your mom' as they "
              "do). They can handle a bit more detail; up to 2 questions per message.",
}


def profile_note(profile: dict | None) -> str | None:
    """The device-held profile, as context for this turn only (it is never stored on the server)."""
    if not profile or not profile.get("people"):
        return None
    return ("SAVED PROFILE from the user's device (confirmed by them earlier; use it, don't re-ask): "
            + json.dumps(profile, default=str)[:6000])


def run_turn_events(messages: list[dict], llm=None, model: str | None = None, lang: str = "en",
                    profile: dict | None = None, mode: str | None = None):
    """Generator of UI events: {"type": "tool_start"|"tool_done"|"plans"|"appeal"|"label"|"profile_update"|"message"}."""
    llm = llm or client()
    model = model or MODELS["agent"]
    convo = messages + [{"role": "system", "content": LANG_NOTE.get(lang, LANG_NOTE["en"])}]
    if mode in MODE_NOTE:
        convo.append({"role": "system", "content": MODE_NOTE[mode]})
    note = profile_note(profile)
    if note:
        convo.insert(len(messages) - 1, {"role": "system", "content": note})  # just before the latest user message
    for _ in range(MAX_STEPS):
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
            yield {"type": "message", "text": msg.content or ""}
            return
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_start", "id": tc.id, "name": tc.function.name, "args": args}
            result = tools.call(tc.function.name, tc.function.arguments)
            trace({"tool": tc.function.name, "args": tc.function.arguments, "result": result[:200000]})
            tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result}
            messages.append(tool_msg)
            convo.append(tool_msg)
            if tc.function.name in ("compare_plans", "read_care_ending_notice") and '"error"' not in result[:50]:
                convo.append({"role": "system", "content": BRIEF_AFTER_CARDS})
            parsed = json.loads(result)
            ok = "error" not in parsed
            yield {"type": "tool_done", "id": tc.id, "name": tc.function.name, "ok": ok,
                   "error": None if ok else parsed["error"]}
            if ok and tc.function.name == "compare_plans":
                yield {"type": "plans", "data": parsed}
            if ok and tc.function.name == "read_care_ending_notice":
                yield {"type": "appeal", "data": parsed}
            if ok and tc.function.name == "read_medicine_label":
                yield {"type": "label", "data": parsed}
            if ok and tc.function.name == "update_profile":
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
