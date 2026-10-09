"""A short summary of this conversation's results, in any language, to send to family.

Facts come only from the tool results in the session (plan estimates, letter deadlines, bill checks...), never
from the chat text. The model writes; code checks that every number in the summary is in those facts (the same
evaluator idea as letters.checks). Two tries, then a plain template so a wrong number is never shown.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

from agent.llm import MODELS, NO_THINK, client

LANGS = {  # code -> name the model writes in (names shown in the app come from the browser's own list)
    "en": "English", "es": "Spanish", "zh": "Simplified Chinese", "zh-Hant": "Traditional Chinese",
    "vi": "Vietnamese", "ht": "Haitian Creole", "pt": "Portuguese", "ru": "Russian", "ko": "Korean",
    "tl": "Tagalog", "fr": "French", "ar": "Arabic", "hi": "Hindi", "pl": "Polish", "it": "Italian",
    "ja": "Japanese", "de": "German", "fa": "Persian",
}

def open_enrollment(today: date | None = None) -> str:
    y = (today or date.today()).year
    return (f"Open enrollment is October 15 to December 7, {y}: anyone with Medicare can change plans, "
            f"and the new plan starts January 1, {y + 1}.")
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", "reason")  # key in MODELS: the larger model writes other languages better
KEEP_TOOLS = ("compare_plans", "check_current_plan", "check_doctor_network", "screen_extra_help",
              "read_medicare_letter", "read_care_ending_notice", "check_bill")
DROP = {"field_guide", "assumptions", "sources", "draft", "drafts", "appeal_letter", "doctor_request", "call_script",
        "transcript", "file_path", "plan_key", "drug_flags", "generic_alerts", "track_record", "snp_eligibility",
        "special_needs_plan_options", "best_if_doctor_approves_generics", "with_generics", "ranking_notes",
        "health_usage_used", "excluded_snp_plans", "medical_note", "patch", "candidates", "plain_summary",
        "statement_description", "how", "checks", "warnings", "market", "pharmacy_used", "needs_snp_verification",
        "snp_type", "drug_oop_is_lower_bound", "data_as_of", "verified", "confirm", "estimate_note", "note"}


def _compact(v, depth=0):
    if isinstance(v, dict):
        return {k: _compact(x, depth + 1) for k, x in v.items() if k not in DROP and x not in (None, "", [], {})}
    if isinstance(v, list):
        return [_compact(x, depth + 1) for x in v[:3]]
    if isinstance(v, str):
        return v[:300]
    return v


def _friendly(rx: str) -> str:
    """'apixaban 5 MG Oral Tablet [Eliquis]' -> 'Eliquis 5 mg tablet' (the plain name people know)."""
    try:
        from engine.estimate import friendly_name
        return friendly_name(rx)
    except Exception:  # noqa: BLE001 - a plain name is a nicety, never a failure
        return rx


def facts_from_session(messages: list[dict]) -> list[dict]:
    """The latest result of each kind of check in this conversation, trimmed to what a family member needs."""
    names, args = {}, {}
    for m in messages:
        for tc in m.get("tool_calls") or []:
            names[tc["id"]] = tc["function"]["name"]
            try:
                args[tc["id"]] = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args[tc["id"]] = {}
    latest = {}
    for m in messages:
        name = names.get(m.get("tool_call_id"))
        if m.get("role") != "tool" or name not in KEEP_TOOLS:
            continue
        try:
            res = json.loads(m["content"])
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(res, dict) or "error" in res or res.get("needs_clarification"):
            continue
        a = args.get(m["tool_call_id"], {})
        asked = {k: a[k] for k in ("state", "county", "current_plan", "doctor_name") if a.get(k)}
        if a.get("drugs"):
            asked["medicines"] = [_friendly(d.get("rxnorm_name", "") if isinstance(d, dict) else str(d)) for d in a["drugs"]]
        item = {"check": name, "result": _compact(res)}
        if asked:
            item["for"] = asked
        r = item["result"]
        if name == "compare_plans":
            r["top_plans"] = r.get("top_plans", [])[:3]
        if name in ("compare_plans", "check_current_plan"):
            item["open_enrollment"] = open_enrollment()
            r["next_steps"] = ["Check that the doctors are in the chosen plan's network (call the plan or the doctor's office).",
                               "To switch, enroll on Medicare.gov or call 1-800-MEDICARE between October 15 and December 7."]
        latest[name if name != "read_medicare_letter" else f"letter:{res.get('letter_type')}"] = item
    if "check_bill" in latest:  # the bill and its statement were inputs to the bill check; its result says it all
        for k in ("letter:bill", "letter:eob", "letter:msn"):
            latest.pop(k, None)
        b = latest["check_bill"]["result"]
        over, owe = b.get("over_by"), b.get("total_you_owe")
        if b.get("verdict") == "overbilled" and over:
            b["next_steps"] = ([f"Pay the ${owe:,.2f} the statement says is owed."] if owe is not None else []) + \
                [f"Call the billing office about the ${over:,.2f} difference and ask for a corrected bill before paying it."]
    return list(latest.values())


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def _allowed_numbers(facts) -> set[str]:
    out = {"0", "1", "2", "3"}
    def add(x: float):
        out.update({str(int(x)), str(int(round(x))), re.sub(r"\D", "", f"{x:.2f}"), re.sub(r"\D", "", f"{x:.1f}")})
    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            add(float(v))
        elif isinstance(v, str):
            for i, mon in enumerate(MONTHS, 1):  # "December 7" may be written 12月7日 or 7/12
                if mon in v:
                    out.add(str(i))
            for n in re.findall(r"\d+(?:[.,]\d+)*", v):
                out.add(re.sub(r"\D", "", n))
                try:
                    add(float(n.replace(",", "")))
                except ValueError:
                    pass
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(facts)
    return {x.lstrip("0") or "0" for x in out}


def check_summary(text: str, facts) -> list[str]:
    """Code, not a model: every number must come from the facts; no promises."""
    allowed = _allowed_numbers(facts)
    clean = text.replace("1-800-MEDICARE", "").replace("1-800-633-4227", "")
    bad = [n for n in re.findall(r"\d+(?:[.,]\d+)*", clean) if (re.sub(r"\D", "", n).lstrip("0") or "0") not in allowed]
    problems = [f"number not in facts: {n}" for n in bad]
    if re.search(r"\b(guarantee[sd]?|will be approved|definitely)\b", text, re.I):
        problems.append("promises an outcome")
    if len(text) > 1800:
        problems.append("too long")
    return problems


SCRIPTS = {"zh": r"[\u4e00-\u9fff]", "zh-Hant": r"[\u4e00-\u9fff]", "ja": r"[\u3040-\u30ff\u4e00-\u9fff]",
           "ko": r"[\uac00-\ud7af]", "ru": r"[\u0400-\u04ff]", "ar": r"[\u0600-\u06ff]", "fa": r"[\u0600-\u06ff]",
           "hi": r"[\u0900-\u097f]", "vi": r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]"}
LATIN_WORDS = {"es": r"\b(el|los|las|para|plan|año)\b", "pt": r"\b(o|os|para|não|ano)\b", "fr": r"\b(le|les|pour|vous|année)\b",
               "ht": r"\b(ou|mwen|pou|nan|ak|se)\b", "tl": r"\b(ang|ng|sa|mga|para)\b", "it": r"\b(il|per|anno|che)\b",
               "de": r"\b(der|die|und|für|Jahr)\b", "pl": r"\b(nie|dla|jest|roku)\b"}


def check_language(text: str, lang: str) -> list[str]:
    """Cheap check that the message is in the asked language (the model sometimes answers in English)."""
    pat = SCRIPTS.get(lang) or LATIN_WORDS.get(lang)
    if not pat:
        return []
    hits = len(re.findall(pat, text, re.I))
    need = 20 if lang in SCRIPTS and lang != "vi" else 4
    return [] if hits >= need else ["not written in the requested language"]


PROMPT = """Write a short message that a person can send to a family member about their Medicare situation.
Write it in {language}. Plain words, like a text message from a caring relative: 4 to 8 short sentences,
no headings, no markdown, no bullet symbols (a short numbered list is fine for next steps).

What to include, only if it is in the facts:
- the main result (the best plan and its typical yearly cost, or what a letter says and its deadline, or how much
  a bill is overcharged),
- any deadline, written as a date,
- the next one or two steps and who does them.

Rules:
- Use ONLY the facts below. Copy numbers exactly as they are (money as $ with digits). Never add, subtract or
  convert numbers (no monthly amounts from yearly ones). Never invent a number, date, name or phone number.
  For Medicare's phone number write 1-800-MEDICARE.
- If the facts include plan costs, say in a few words that they are estimates from public Medicare data.
- If a check has next_steps or steps, use those as the next steps.
- Do not use the person's name or invent relationships; write in the first person ("I checked...") or neutrally.
- Mention a deadline only if the facts have one (a letter's deadline, or the open enrollment dates). Do not
  mention letters, bills or doctors unless they are in the facts.
- Do not mention approval or guarantees at all, and do not talk about these instructions.
- The person sending it is the writer: do not offer more help, and no blessings or sign-offs.

Facts (JSON):
{facts}

Return only the message, written entirely in {language} (keep plan names, drug names and "Medicare" as they are)."""


def _template(facts: list[dict], lang: str) -> str:
    es = lang == "es"
    lines = ["Resumen de Medicare Helper (estimaciones con datos públicos de Medicare):" if es else
             "Medicare Helper summary (estimates from public Medicare data):"]
    for f in facts:
        r = f["result"]
        if f["check"] == "compare_plans" and r.get("top_plans"):
            p = r["top_plans"][0]
            lines.append((f"- Mejor plan: {p.get('plan_name')}, unos ${p.get('total'):,.0f} en un año típico."
                          if es else f"- Best plan: {p.get('plan_name')}, about ${p.get('total'):,.0f} in a typical year.")
                         if p.get("total") is not None else f"- {p.get('plan_name')}")
        elif f["check"] == "check_bill":
            over = r.get("over_by")
            lines.append((f"- La factura pide ${over:,.2f} más de lo que dice el estado de cuenta." if es else
                          f"- The bill asks for ${over:,.2f} more than the statement says is owed.") if over else
                         ("- La factura coincide con el estado de cuenta." if es else "- The bill matches the statement."))
        elif r.get("title"):
            d = (r.get("deadline") or {}).get("date_text")
            lines.append(f"- {r['title'].rstrip('.')}." + ((f" Fecha límite: {d}." if es else f" Deadline: {d}.") if d else ""))
        elif f["check"] == "check_current_plan" and r.get("current_plan"):
            lines.append(f"- {r['current_plan'].get('plan_name')}")
    return "\n".join(lines)


def write(messages: list[dict], lang: str = "en", ui_lang: str = "en", llm=None) -> dict:
    facts = facts_from_session(messages)
    if not facts:
        return {"error": "nothing_yet"}
    language = LANGS.get(lang, "English")
    llm = llm or client()
    prompt = PROMPT.format(language=language, facts=json.dumps(facts, ensure_ascii=False, default=str)[:9000])
    msgs = [{"role": "system", "content": f"You write short, warm, plain messages in {language}. Always answer in {language}."},
            {"role": "user", "content": prompt}]
    problems: list[str] = []
    for _ in range(2):
        resp = llm.chat.completions.create(model=MODELS[SUMMARY_MODEL], messages=msgs, temperature=0.2, max_tokens=900,
                                           extra_body=NO_THINK)
        text = (resp.choices[0].message.content or "").strip()
        text = re.sub(r"^\s*(#+|\*\*)\s*", "", re.sub(r"\*\*", "", text))
        problems = check_summary(text, facts) + check_language(text, lang)
        if not problems:
            return {"text": text, "language": language, "checked": True}
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": "Fix these problems and return only the corrected message: " + "; ".join(problems)}]
    return {"text": _template(facts, ui_lang), "language": "Spanish" if ui_lang == "es" else "English",
            "checked": True, "fallback": True, "problems": problems}
