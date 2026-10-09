"""Any Medicare letter -> type, key facts, deadline, steps, and a drafted appeal letter.

    PYTHONPATH=src python -m letters.read evals/fixtures/letters/partd_denial.png --today 2026-10-09

Router: keywords for the standard CMS / SSA notice titles (no LLM), LLM only for letters with no known title.
Per type: Lightning extracts fields (thinking off) -> rules.plan() adds deadline + steps -> Super drafts ONE
argument paragraph -> check_draft() rejects any number/date not in the facts or a promise of approval; one redraft,
then a plain fallback paragraph. Care-ending notices go to the existing defend.notice pipeline.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agent.llm import MODELS, NO_THINK, client
from defend.notice import _json, _parse_date, transcribe
from letters.checks import check_draft, keyword_type
from letters.rules import fmt, plan

TYPES = ["nomnc", "partd_denial", "ma_denial", "msn", "irmaa", "anoc", "eob", "other"]
def classify(text: str, llm=None) -> tuple[str, str]:
    """(type, how): 'keyword' when an official title is found, else 'llm'."""
    kind = keyword_type(text)
    if kind:
        return kind, "keyword"
    llm = llm or client()
    resp = llm.chat.completions.create(model=MODELS["extract"], temperature=0, max_tokens=200, extra_body=NO_THINK, messages=[{
        "role": "user", "content": "Which kind of US Medicare letter is this? Answer with JSON {\"type\": one of "
        + json.dumps(TYPES) + "}. partd_denial = a drug plan refused a prescription; ma_denial = a Medicare Advantage plan "
        "refused medical care or payment; msn = Original Medicare claim summary; irmaa = Social Security income-related "
        "premium; anoc = plan changes for next year; eob = plan's explanation of benefits.\n\nLetter:\n" + text[:6000]}])
    kind = _json(resp.choices[0].message.content).get("type")
    return (kind if kind in TYPES else "other"), "llm"


FIELDS = {
    "partd_denial": '{"plan_name", "plan_phone", "item": the drug denied (name and strength), "denial_reason": the reason, '
                    'quoted briefly, "notice_date": "YYYY-MM-DD" (date on the notice), "notice_date_as_written", '
                    '"member_first_name", "request_kind": "prior_authorization"|"exception"|"quantity_limit"|"step_therapy"|"other"}',
    "ma_denial": '{"plan_name", "plan_phone", "item": the care, service or item denied, "denial_reason": the reason, quoted '
                 'briefly, "notice_date": "YYYY-MM-DD", "notice_date_as_written", "member_first_name", '
                 '"when": "before_care"|"payment"|"part_b_drug"}',
    "msn": '{"appeal_by": "YYYY-MM-DD" (the date you must appeal by), "appeal_by_as_written", "items_denied": [short list], '
           '"notice_date": "YYYY-MM-DD", "member_first_name"}',
    "irmaa": '{"notice_date": "YYYY-MM-DD", "notice_date_as_written", "premium_year", "tax_year_used", "member_first_name"}',
    "anoc": '{"plan_name", "plan_id": like "H1234-056" if printed, "plan_year"}',
    "eob": '{"plan_name", "period"}',
    "other": '{"sender", "subject": one line, "date": "YYYY-MM-DD"}',
}


def extract(kind: str, text: str, llm=None) -> dict:
    llm = llm or client()
    prompt = (f"From this Medicare letter, return ONLY a JSON object with keys {FIELDS[kind]}. Use null when not printed. "
              "Copy names, phone numbers and dates exactly as printed.\n\nLetter:\n" + text[:12000])
    resp = llm.chat.completions.create(model=MODELS["extract"], temperature=0, max_tokens=1500, extra_body=NO_THINK,
                                       messages=[{"role": "user", "content": prompt}])
    f = _json(resp.choices[0].message.content)
    for k, v in list(f.items()):  # models sometimes nest {"name":..,"strength":..}: flatten to plain text
        if isinstance(v, dict):
            f[k] = " ".join(str(x) for x in v.values() if x)
    for k in ("notice_date", "appeal_by", "date"):  # normalize dates; trust the printed text over the model
        written = f.get(f"{k}_as_written")
        d = _parse_date(written) or _parse_date(f.get(k))
        f[k] = d.isoformat() if d else None
    return f


def verify(f: dict, text: str) -> list[str]:
    """Fields to ask the user to confirm: a date or phone that can't be found in the transcript."""
    low, digits = text.lower(), re.sub(r"\D", "", text)
    ask = []
    for k in ("notice_date", "appeal_by"):
        if f.get(k):
            d = date.fromisoformat(f[k])
            forms = {(f.get(f"{k}_as_written") or "").lower(), f"{d:%B} {d.day}, {d.year}".lower(), f"{d.month}/{d.day}/{d.year}",
                     f"{d:%m/%d/%Y}", f"{d.month}/{d.day}/{d:%y}"} - {""}
            if not any(x in low for x in forms):
                ask.append(k)
    if f.get("plan_phone") and re.sub(r"\D", "", f["plan_phone"])[-10:] not in digits:
        ask.append("plan_phone")
    return ask


DRAFT = """Write ONE short paragraph (3-5 sentences, plain English, first person, polite and firm) for {what},
answering {whose} stated reason. Use ONLY these facts. You do NOT know this person's medical history:
never say they tried, took, failed or could not tolerate anything, never say what their doctor found, and never claim
anything about how the plan handled the case. Every personal or medical detail goes in a short bracketed instruction
the person fills in before sending, like [say what happened when you tried metformin, or why you can't take it].
No new numbers or dates. Do not promise or predict the outcome. Output only the paragraph.

Example (different case): "I am asking you to reconsider your decision on Eliquis 5 mg. You said the drug needs prior
authorization. My doctor prescribed it because [say why you need it, e.g. the condition it treats]. [If you tried
another blood thinner, say which one and what happened.] My doctor is sending a statement supporting this request."

Facts: {facts}"""
WHAT = {
    "partd_denial": ("a Medicare drug plan appeal letter (redetermination)", "the plan's"),
    "ma_denial": ("a Medicare Advantage appeal letter (reconsideration)", "the plan's"),
    "msn": ("an Original Medicare appeal letter (redetermination) about the denied items", "Medicare's"),
    "irmaa": ("a request to Social Security to reconsider the income it used for the higher premium (IRMAA); the point "
              "is that the income used is wrong or no longer reflects current income", "Social Security's"),
}
FALLBACK = ("I am asking you to reconsider this decision. {item} was prescribed by my doctor because [why I need it]. "
            "[What happened with other options, if any.] My doctor is sending a supporting statement. Please review my case.")


def draft_argument(kind: str, f: dict, llm=None) -> tuple[str, dict]:
    llm = llm or client()
    facts = {k: f.get(k) for k in ("plan_name", "item", "denial_reason", "request_kind", "when", "items_denied", "tax_year_used")
             if f.get(k)}
    note, tries = "", []
    for _ in range(2):
        what, whose = WHAT.get(kind, WHAT["partd_denial"])
        resp = llm.chat.completions.create(model=MODELS["agent"], temperature=0.2, max_tokens=500, extra_body=NO_THINK,
                                           messages=[{"role": "user", "content": DRAFT.format(facts=json.dumps(facts), what=what, whose=whose) + note}])
        par = re.sub(r"<think>.*?</think>", "", resp.choices[0].message.content or "", flags=re.S).strip()
        problems = check_draft(par, facts)
        tries.append(problems)
        if par and not problems:
            return par, {"checked": True, "attempts": len(tries)}
        note = "\n\nYour last draft had problems: " + "; ".join(problems) + ". Fix them."
    return FALLBACK.format(item=f.get("item") or "This"), {"checked": True, "attempts": len(tries), "fallback": True}


def appeal_letter(kind: str, f: dict, argument: str, today: date) -> str:
    """The letter itself is a fixed template (English: it goes to the plan / Social Security); only the middle
    paragraph is written by the model and checked above."""
    if kind == "irmaa":
        head = ("To: Social Security Administration\nRe: Request for reconsideration of my income-related monthly "
                f"adjustment amount (IRMAA){' for ' + str(f['premium_year']) if f.get('premium_year') else ''}\n")
        ask = "I request a reconsideration of this determination."
    elif kind == "msn":
        head = "To: Medicare Administrative Contractor (address on the last page of my Medicare Summary Notice)\nRe: Redetermination request\n"
        ask = ("I request a redetermination of the following items on my Medicare Summary Notice"
               f"{' dated ' + fmt(date.fromisoformat(f['notice_date'])) if f.get('notice_date') else ''}: "
               f"{', '.join(f.get('items_denied') or ['[items]'])}.")
    else:
        what = "redetermination" if kind == "partd_denial" else "reconsideration"
        head = (f"To: {f.get('plan_name') or '[plan name]'} - Appeals\n"
                f"Re: Request for {what} of the denial of {f.get('item') or '[drug or service]'}\n")
        ask = (f"I am asking for a {what} of your decision"
               f"{' dated ' + fmt(date.fromisoformat(f['notice_date'])) if f.get('notice_date') else ''} "
               f"denying coverage of {f.get('item') or '[drug or service]'}. "
               "[If waiting could seriously harm my health: Please treat this as a FAST (expedited) appeal.]")
    return (f"{fmt(today)}\n\n{head}Member: [your full name]   Medicare / plan member ID: [from your card]\n\n"
            f"{ask}\n\n{argument}\n\nThank you,\n[Your name]\n[Your phone]\n[Your address]\n\n"
            "Enclosed: a copy of the notice[, my doctor's statement]")


def analyze(path: str, today: date | None = None, lang: str = "en", llm=None, text: str | None = None) -> dict:
    llm = llm or client()
    today = today or datetime.now(ZoneInfo("America/New_York")).date()
    from agent import metrics
    if text is None:
        with metrics.task("letter.transcribe"):
            text = transcribe(Path(path), llm)
    with metrics.task("letter.classify"):
        kind, how = classify(text, llm)
    if kind == "nomnc":  # the care-ending pipeline already exists; reuse it on the same transcript
        from defend.notice import analyze as analyze_nomnc
        out = analyze_nomnc(path, llm=llm, lang=lang, text=text)
        out["letter_type"], out["classified_by"] = "nomnc", how
        return out
    with metrics.task("letter.extract"):
        f = extract(kind, text, llm)
    out = plan(kind, f, today, lang)
    out.update(fields=f, classified_by=how, needs_user_confirmation=verify(f, text))
    if kind in ("partd_denial", "ma_denial", "msn", "irmaa"):
        with metrics.task("letter.draft"):
            arg, info = draft_argument(kind, f, llm)
        out["appeal_letter"], out["draft_check"] = appeal_letter(kind, f, arg, today), info
    return out


if __name__ == "__main__":
    today = date.fromisoformat(sys.argv[sys.argv.index("--today") + 1]) if "--today" in sys.argv else None
    print(json.dumps(analyze(sys.argv[1], today=today), indent=1, default=str))
