"""Medicare Choose-mode agent: Nemotron Super plans + calls deterministic tools; never invents numbers.

    PYTHONPATH=src python -m agent.agent            # interactive chat in the terminal
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
import time
from pathlib import Path

from agent import metrics, tools
from agent.llm import MODELS, client

SYSTEM = """You are a neutral, privacy-first Medicare helper for older adults and the family members who help them.
You are NOT an insurance agent or broker, you earn nothing from any plan, and you do not enroll anyone.

How you work:
0. ALWAYS answer the user's latest question or request first, in one or two sentences, even while details are
   still missing (e.g. "I can't enroll you, but ..."; "I'll check that doctor once we have the plans"). Then ask
   only for what you still need.
1. Gather: where they live (state + county), each medication with strength and how many per month.
   The county tells you the state (Broward or Miami-Dade = Florida): never ask for the state then.
   Medicaid: if they didn't mention it, assume no Medicaid, say so in a few words ("assuming no Medicaid"), and go on.
   Hospital stays: don't hold up the comparison for it. Run compare_plans first; you may ask afterwards, once:
   "Any hospital stays in the past year?" Do NOT ask people to rate their health care use as low/medium/high -
   compare_plans estimates it from their medicines and conditions.
   NEVER ask the user to confirm what they just told you ("Is that correct?", "Just to confirm..."): use it.
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
   SEVERAL PEOPLE (e.g. Mom and Dad): compare plans separately for each person (one compare_plans per person, with
   only that person's medicines) and report each by name.
   Quantities you work out (insulin units -> mL or pens, eye drops -> bottles, "twice a day" -> 60) or a strength you
   assume: say them in a few words ("I used 6 mL, 2 pens, a month") so the user can correct you.
2. Use find_drug to turn each medication into an exact RxNorm name; confirm strength with the user if unclear.
   Use find_county if the county name might not match exactly.
3. Call compare_plans. ALL dollar amounts, dates, star ratings and coverage facts must come from tool results
   in THIS conversation - never from memory (e.g. use part_b_monthly_premium from the tool, never a remembered
   Part B amount). If a number is not in a tool result, don't state it.
4. Explain the top 2-3 regular plans first (top_plans), then mention special-needs plans only if any are listed
   (they require the plan to confirm eligibility). For each: typical-year cost, bad-year cost, star rating, and
   any drug that is NOT covered. Use the field_guide to describe numbers correctly. Lower bound = at least this much.
5. For each plan you discuss, include every item from its plain_summary: uncovered drugs and each generic
   alert WITH its dollar amount ("ask the doctor about ..."). Never tell anyone to change medication themselves. Mention the data date and the key assumptions briefly.
6. If a_regular_plan_covers_every_drug_as_prescribed is false, say that plainly first ("no plan covers all their
   medicines exactly as prescribed"), and never call a plan "cheapest" when its cost is a lower bound. Then
   present the best of best_if_doctor_approves_generics as the option to discuss with their doctor.
7. End with concrete next steps: verify doctors are in network (call the plan), compare on Medicare.gov or call
   1-800-MEDICARE, and for complicated situations the free local SHIP counselor.
WHAT-IF questions ("what if they use mail order", "what if they have a hard year", "what if we add a medicine"):
call compare_plans again with ONLY that input changed (pharmacy, hospital_stay_last_year / health_usage, drugs),
then say in 2-3 sentences what changed versus the previous result (best plan, typical-year cost). Don't restate
everything. "Why is this plan first?": explain with ranking_notes and the field_guide ranking assumption.
DOCTORS: when asked whether a doctor is in network, call check_doctor_network with the organizations of the plans
you discussed. If it returns needs_clarification, list the matches in plain words (name, specialty, city) and ask
which one; then call again with specialty. Report per plan: "found on the insurer's directory" / "mentioned online" / "no listing found (that
does not mean out of network)". If npi_registry_matches has several doctors, ask which one (specialty, city). Never
say a doctor IS in network; always end with: call the plan or the doctor's office to confirm before enrolling.
CURRENT PLAN: if the user says which plan the person has now, or asks whether to stay, call check_current_plan INSTEAD
of compare_plans (it already includes the best alternative); call compare_plans too only if they also want the full list. Lead
with the verdict in one sentence (stay / worth switching and the typical-year savings), then next year's published
changes (premium, out-of-pocket max; say plainly if the plan is not continuing), then any of their drugs the insurer
dropped last year. If needs_clarification, show the candidates and ask which one. Once identified, save it with
update_profile (current_plan = the plan_key, current_plan_name = its name) so nobody has to say it again.
EXTRA HELP: if someone may have limited income, or asks, offer the Extra Help check (screen_extra_help). If they
already gave income and savings, call screen_extra_help right away; medicines are optional for it. Explain
the result plainly ("you may qualify" - Social Security decides), the rough drug cost with Extra Help if given, and
how to apply (online or phone from the tool). Plan comparisons do not yet include Extra Help pricing - don't
offer to re-run them "with Extra Help". Income and savings are private: never call update_profile with them.
NOT A MEDICARE DOCUMENT: if read_medicare_letter returns letter_type "not_medicare", say in one sentence what the photo
looks like (looks_like), that it doesn't seem to be a Medicare letter, bill or statement, and what you can read: Medicare
or plan letters and notices, bills with the plan's EOB or Medicare's MSN, and pill bottle labels. Ask for the right photo.
Do not guess its contents.
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
- Each question is one short line with an easy example answer, e.g. "How many Synthroid pills do they take a day? (Most people take 1.)"
- Don't ask for what you can look up or reasonably assume: strength shown on the name, insulin pens usually come 5 per box
  (say what you assumed and let them correct it). Fill in common defaults and say so, rather than asking.
- Never re-ask or ask to confirm something the user already told you (e.g. "5 pens a month"). If they gave a
  number, use it and go straight to the tools. "Twice a day" / "once a day" / "at night" is a count: one pill each
  time (twice a day = 60 a month) unless they said otherwise; don't ask again.
- Never show internal plan keys like "H1036-054-000"; say the plan name and its ID "H1036-054".
- Briefly state what you already know in one sentence before asking, e.g. "Got it: Tampa, no Medicaid." - a statement,
  never a question.
- Only offer what your tools can do. You do not have plans' phone numbers or websites: for enrolling or plan contact
  details, point to Medicare.gov Plan Finder or 1-800-MEDICARE.
- Only call a plan "your current plan" if check_current_plan identified it. """

BRIEF_AFTER_CARDS = (
    "The app is now showing the full results as cards. Your reply must be at most 5 short sentences, no headings, "
    "no bullet lists, no repeated numbers for every plan. Say: (1) the single best option and its typical-year cost; "
    "if a generic switch makes another plan cheaper, say that too (use with_generics totals); (2) one sentence from "
    "ranking_notes if present; (3) any drug that needs prior authorization on that plan; (4) the one next step. "
    "If special-needs plans are listed and the person has Medicaid or one of the listed conditions, add one sentence "
    "that special-needs plans are available for them and the plan must confirm eligibility. "
    "For care-ending notices: the deadline first, then who to call. For doctor checks: one sentence on which plans "
    "list the doctor, then: call the plan or the doctor's office to confirm. NEVER use tables.")

MAX_STEPS = 8
MAX_REPAIRS = 2  # rewrites per turn; a table that survives them is flattened in code


def flatten_tables(text: str) -> str:
    """Last resort: markdown table -> one plain line per row ('A - B - C'), header and divider dropped."""
    out, rows = [], []
    for line in (text or "").split("\n"):
        if re.match(r"^\s*\|.*\|\s*$", line):
            rows.append(line)
            continue
        if rows:
            out += _table_lines(rows)
            rows = []
        out.append(line)
    if rows:
        out += _table_lines(rows)
    return "\n".join(out)


def _table_lines(rows: list[str]) -> list[str]:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    body = [c for i, c in enumerate(cells) if i > 0 and not all(re.fullmatch(r":?-{2,}:?", x or "-") for x in c)]
    return ["- " + " - ".join(x for x in c if x) for c in body if any(c)]

PLAN_ID = re.compile(r"\bH\d{4}-\d{3}\b", re.I)
STAY = re.compile(r"\bstay\b.{0,40}\bplan\b|\bplan\b.{0,40}\bstay\b|\bkeep (my|her|his|their|our) plan\b|"
                  r"\bcurrent plan\b|\bthe plan (i|she|he|they|we|mom|dad) (have|has|am in|is in)\b", re.I)
PLAN_KEY = re.compile(r"\b([HSR]\d{4}[-\u2010-\u2011]\d{3})[-\u2010-\u2011]\d{3}\b")
TABLE = re.compile(r"^\s*\|.*\|\s*$\n^\s*\|?\s*:?-{3,}", re.M)
RECONFIRM = re.compile(r"(is that|is this|that's|are those|(does|do) (that|this|these|those) (sound|look)) (still )?"
                       r"(correct|right|accurate)\b[^.?!\n]{0,60}\?|just to confirm|can you confirm\b", re.I)
# asking where the PERSON lives (not where a doctor practices)
ASKS_LOCATION = re.compile(r"\b(which|what) (specific )?(county|zip( code)?|city|town|area)\b[^.!?\n]*\b(you|she|he|they)\b[^.!?\n]*\blives?\b[^.!\n]*\?|"
                           r"\b(your|her|his|their) (county|zip( code)?|city|town)\b[^.!\n]*\?|"
                           r"\bwhere (do|does) (you|she|he|they) live\b|"
                           r"\b(are|is|does|do) (you|she|he|they|your \w+) (in|live in|near)\b[^.!\n]*\?", re.I)
DONT_KNOW = re.compile(r"\b(i )?(don't|do not|dont) know\b|\bnot sure\b|\bno s[eé]\b", re.I)
# Medicare Beneficiary Identifier: 11 characters, e.g. 1EG4-TE5-MK73
MBI = re.compile(r"\b[1-9][A-Z][A-Z0-9]\d-?[A-Z][A-Z0-9]\d-?[A-Z]{2}\d{2}\b", re.I)
SAYS_NOT_SAVED = re.compile(r"(not|n't|never|no)\b.{0,40}(save|store|keep|record|guard)", re.I)
NOT_SAVED = {"en": "I don't save Medicare numbers, and I don't need yours to compare plans, so keep it private.",
             "es": "No guardo números de Medicare y no necesito el suyo para comparar planes; manténgalo privado."}
ASKS_PROMISE = re.compile(r"\b(promise|guarantee|garant\w*|prom[eé]t\w*)\b", re.I)
SAYS_ESTIMATE = re.compile(r"\b(estimate|guarantee|promise|estimad\w*|garant\w*|prome\w*)", re.I)
NO_PROMISE = {"en": "These are estimates, not a promise: plans and prices can change each year.",
              "es": "Son estimaciones, no una promesa: los planes y los precios pueden cambiar cada año."}
PRICED_AS = {"en": "I priced {name} at {qty} mL a month; check that this matches the prescription.",
             "es": "Calculé {name} con {qty} mL al mes; confirme que coincide con la receta."}


def polish(text: str) -> str:
    """Internal plan keys 'H1019-001-000' -> the plan ID people see, 'H1019-001' (prompt rule the model sometimes breaks)."""
    return PLAN_KEY.sub(r"\1", text or "")


def _last_user(messages: list[dict] | None) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return ""


def _prev_assistant(messages: list[dict] | None) -> str:
    """The assistant reply shown before the latest user message."""
    seen_user = False
    for m in reversed(messages or []):
        if m.get("role") == "user":
            seen_user = True
        elif seen_user and m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
            return m["content"]
    return ""


@functools.lru_cache(maxsize=1)
def _known_counties() -> frozenset[str]:
    try:
        return frozenset(c.lower().replace(" county", "") for _, c in tools.data.counties(tools.data.connect()))
    except Exception:  # no database: only "<Name> County" in the text counts
        return frozenset()


def gave_county(messages: list[dict] | None) -> bool:
    """Did the user already name a county (Broward, Miami-Dade, 'Cook County')?"""
    text = " ".join(m["content"] for m in messages or [] if m.get("role") == "user" and isinstance(m.get("content"), str))
    text = text.lower().replace("\u2011", "-").replace("\u2010", "-")
    if re.search(r"\b[a-z][a-z.' -]{2,30} county\b", text):
        return True
    return any(re.search(rf"\b{re.escape(c)}\b", text) for c in _known_counties() if len(c) > 3)


def style_problem(text: str, messages: list[dict] | None = None) -> str | None:
    """Prompt rules the model breaks often enough to fix in code (found by evals/agent): one rewrite is requested."""
    text = (text or "").replace("\u2019", "'")
    if TABLE.search(text or ""):
        return "It uses a table. Never use tables: use short plain sentences or a short numbered list."
    if RECONFIRM.search(text or ""):
        return ("It asks the user to confirm facts they already gave. Don't: use what they said, state any assumption "
                "in a few words, and continue (call the tools you need now).")
    if ASKS_LOCATION.search(text) and gave_county(messages):
        return ("The user already named their county, which is all compare_plans needs (it also tells you the state). "
                "Do not ask for a city, ZIP code or county again: call find_county / compare_plans now.")
    if "?" in text and DONT_KNOW.search(_last_user(messages)) and "?" in _prev_assistant(messages):
        return ("The user just said they don't know. Do not ask that again in other words. Use the usual default "
                "(for example: no Medicaid, Original Medicare, 30 tablets a month), say the assumption in a few words, "
                "and continue now with the tools. Ask a different question only if something essential, like the county, "
                "is still missing.")
    return None


def _short_name(rxnorm_name: str) -> str:
    m = re.search(r"\[([^\]]+)\]", rxnorm_name)
    return m.group(1) if m else re.sub(r"\s+\d.*$", "", rxnorm_name).strip() or rxnorm_name


def add_required_notes(text: str, messages: list[dict] | None, priced: list[dict], lang: str = "en") -> str:
    """Facts every reply must carry, added in code because the prompt rule alone was not reliable."""
    lang = lang if lang in NOT_SAVED else "en"
    notes = []
    for d in priced:  # liquids and pens: say the quantity we assumed (e.g. 20 units/day of 100 units/mL -> 6 mL)
        name, qty = d.get("rxnorm_name", ""), d.get("qty_per_30d")
        if "/ML" in name.upper() and qty:
            q = int(qty) if float(qty).is_integer() else qty
            if not re.search(rf"\b{re.escape(str(q))}\s*(ml|pens?)\b", text, re.I):
                notes.append(PRICED_AS[lang].format(name=_short_name(name), qty=q))
    if ASKS_PROMISE.search(_last_user(messages)) and not SAYS_ESTIMATE.search(text):
        notes.append(NO_PROMISE[lang])
    if MBI.search(_last_user(messages)) and not SAYS_NOT_SAVED.search(text.replace("\u2019", "'")):
        notes.append(NOT_SAVED[lang])
    return (text.rstrip() + "\n\n" + " ".join(notes)) if notes else text


RXNORM_NAME = re.compile(r'"rxnorm_name":\s*"((?:[^"\\]|\\.)*)"')


def _tool_names(messages: list[dict]) -> dict:
    return {tc["id"]: tc["function"]["name"] for m in messages if m.get("tool_calls") for tc in m["tool_calls"]}


def guard(name: str, args: dict, messages: list[dict], profile: dict | None = None) -> str | None:
    """Rules the prompt states but the model sometimes skips, enforced in code. Returns an error for the model, or None.
    Found by evals/agent: the model typed 'metformin 500 MG Oral Tablet' without find_drug (3 of 4 runs), and answered
    'should I stay in H1019-006?' with compare_plans, then called the top-ranked plan 'your current plan'."""
    if name in ("compare_plans", "check_current_plan"):
        ids = _tool_names(messages)
        known = set()
        for m in messages:
            if m.get("role") == "tool" and ids.get(m.get("tool_call_id")) in ("find_drug", "read_medicine_label"):
                known.update(json.loads(f'"{x}"') for x in RXNORM_NAME.findall(m.get("content") or ""))
        for person in (profile or {}).get("people", []):
            known.update(str(d.get("rxnorm_name")) for d in person.get("medicines", []))
        missing = [d.get("rxnorm_name") for d in args.get("drugs") or [] if d.get("rxnorm_name") not in known]
        if missing:
            return ("Not run: call find_drug for each of these first and use an rxnorm_name it returns, exactly: "
                    + "; ".join(map(str, missing)) + ". Never type a drug name yourself.")
    if name == "compare_plans":
        last_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)
        text = messages[last_user]["content"] if last_user >= 0 else ""
        ids = _tool_names(messages[last_user:])
        checked = any(ids.get(m.get("tool_call_id")) == "check_current_plan" for m in messages[last_user:] if m.get("role") == "tool")
        anoc = None
        ids_all = _tool_names(messages)
        for m in messages:
            if m.get("role") == "tool" and ids_all.get(m.get("tool_call_id")) == "read_medicare_letter":
                try:
                    out = json.loads(m.get("content") or "{}")
                except json.JSONDecodeError:
                    continue
                pid = (out.get("fields") or out).get("plan_id") if isinstance(out, dict) else None
                if out.get("letter_type") == "anoc" and pid:
                    anoc = pid
            if m.get("role") == "tool" and ids_all.get(m.get("tool_call_id")) == "check_current_plan":
                anoc = None  # already checked after the notice
        if anoc:
            return (f"Not run: the user's Annual Notice of Change is for plan {anoc}. Call check_current_plan with "
                    f"current_plan='{anoc}' first; it already includes the best alternative.")
        if (PLAN_ID.search(text) or STAY.search(text)) and not checked:
            return ("Not run: the user is asking about the plan they have now. Call check_current_plan first (it already "
                    "includes the best alternative). Never call a plan 'your current plan' unless check_current_plan "
                    "identified it.")
    return None
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
    "family": "The user is a family member or helper managing someone else's Medicare (refer to the person the way the user does - their name, "
              "'your dad', 'she' - and use 'they' until you know; never assume). They can handle a bit more detail; up to 2 questions per message.",
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
    repairs = 0
    priced: list[dict] = []  # compare_plans drugs this turn, for add_required_notes
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
            problem = style_problem(msg.content or "", messages[:-1])
            if problem and repairs < MAX_REPAIRS:  # bounded rewrites, never a loop
                repairs += 1
                messages.pop()
                convo.pop()
                convo.append({"role": "system", "content": "Your draft reply was not sent. " + problem +
                              " Draft:\n" + (msg.content or "")})
                continue
            msg.content = add_required_notes(polish(flatten_tables(msg.content or "")), messages, priced, lang)
            messages[-1]["content"] = msg.content
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
            blocked = guard(tc.function.name, args, messages, profile)
            if tc.function.name == "compare_plans" and not blocked:
                priced = [d for d in args.get("drugs") or [] if isinstance(d, dict)]
            result = json.dumps({"error": blocked}) if blocked else tools.call(tc.function.name, tc.function.arguments, lang=lang)
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
                elif parsed.get("letter_type") not in ("bill", "eob", "not_medicare"):  # those lead to check_bill; the message covers them
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
