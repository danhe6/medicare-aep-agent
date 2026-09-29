"""Read a prescription bottle / pharmacy label photo and turn it into a medication entry.

    PYTHONPATH=src python -m meds.label evals/fixtures/rx_label_sample.png

Pipeline (same pattern as defend.notice): Gemma 3 vision transcribes the label -> Nemotron extracts fields as JSON
-> deterministic checks (drug name and numbers must appear in the transcript) -> quantity per 30 days computed in
code from quantity + days supply, or from the directions ("take 1 tablet twice daily") -> RxNorm lookup.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from agent.llm import MODELS, client
from defend.notice import _json, transcribe
from engine import rxnorm
from engine.estimate import friendly_name

EXTRACT_PROMPT = """From this prescription label text, return ONLY a JSON object (null if not shown):
{"drug_name": "medicine name exactly as printed, e.g. 'Jardiance' or 'Metformin HCl'",
 "strength": "e.g. '25 mg', '100 units/mL'",
 "dose_form": "tablet | capsule | pen | vial | inhaler | eye drops | liquid | patch | other",
 "directions": "the SIG exactly as printed, e.g. 'Take 1 tablet by mouth twice daily'",
 "quantity": number dispensed (number only), "quantity_unit": "tablets | capsules | mL | pens | ...",
 "days_supply": number or null, "refills": number or null,
 "pharmacy_name": string, "fill_date": "YYYY-MM-DD" or null}
Label text:
"""

_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "half": 0.5, "1/2": 0.5, "½": 0.5}
_FREQ = [(r"four times (a|per) day|\bqid\b", 4), (r"three times (a|per) day|\btid\b", 3),
         (r"twice (a |per )?day|twice daily|two times (a|per) day|\bbid\b|every 12 hours", 2),
         (r"every 8 hours", 3), (r"every 6 hours", 4), (r"every other day", 0.5),
         (r"once (a )?week|weekly|every week", 1 / 7),
         (r"once (a |per )?day|once daily|\bdaily\b|every day|at bedtime|every morning|every evening|\bqd\b", 1)]


def per_day_from_directions(sig: str | None) -> float | None:
    """'Take 1 tablet by mouth twice daily' -> 2.0 units/day. None if unclear (e.g. 'as needed', sliding scale)."""
    if not sig or re.search(r"as needed|\bprn\b|sliding scale|as directed", sig, re.I):
        return None
    s = sig.lower()
    m = re.search(r"take\s+(\d+(?:\.\d+)?|one|two|three|four|half|1/2|½)\s+(tablet|capsule|pill|tab|cap)", s)
    if not m:
        return None
    n = float(_NUM.get(m.group(1), m.group(1)))
    for pat, f in _FREQ:
        if re.search(pat, s):
            return n * f
    return None


def qty_per_30d(fields: dict) -> tuple[float | None, str]:
    q, days = fields.get("quantity"), fields.get("days_supply")
    try:
        if q and days and float(days) > 0:
            return round(float(q) / float(days) * 30, 1), f"{q} {fields.get('quantity_unit') or ''} for {days} days".strip()
    except (TypeError, ValueError):
        pass
    m = re.search(r"inject\s+(\d+)\s+units", (fields.get("directions") or "").lower())
    if m:  # insulin: units/day -> mL per 30 days (U-100 unless the strength says 200 units/mL)
        f = next((mult for pat, mult in _FREQ if re.search(pat, fields["directions"].lower())), None)
        conc = 200 if "200" in str(fields.get("strength") or "") else 100
        if f:
            return round(float(m.group(1)) * f * 30 / conc, 1), f"mL from directions: {fields['directions']}"
    per_day = per_day_from_directions(fields.get("directions"))
    if per_day:
        return round(per_day * 30, 1), f"from directions: {fields['directions']}"
    return None, "not clear from the label"


def _in_text(value, text: str) -> bool:
    if value in (None, ""):
        return False
    v = str(value).lower()
    v = re.sub(r"\.0$", "", v)
    return v in text.lower()


def analyze(path: str, llm=None) -> dict:
    llm = llm or client()
    text = transcribe(Path(path), llm)
    fields = {}
    for role in ("extract", "agent"):
        resp = llm.chat.completions.create(model=MODELS[role], temperature=0, max_tokens=4000,
                                           messages=[{"role": "user", "content": EXTRACT_PROMPT + text}])
        fields = _json(resp.choices[0].message.content or "")
        if fields.get("drug_name"):
            break
    if not fields.get("drug_name"):
        return {"error": "I couldn't read the medicine name. Ask the user for a clearer photo of the label, "
                         "or to type the name and strength."}
    qty, how = qty_per_30d(fields)
    checks = {"drug_name_found_in_text": _in_text(fields.get("drug_name"), text),
              "quantity_found_in_text": _in_text(fields.get("quantity"), text) if fields.get("quantity") else None}
    query = " ".join(str(x) for x in (fields.get("drug_name"), fields.get("strength"), fields.get("dose_form")) if x)
    matches = rxnorm.search(query, limit=5)
    # Keep only products whose strength matches the label ("25 mg" -> "25 MG"), and the brand if one is printed.
    num = re.findall(r"\d+(?:\.\d+)?", str(fields.get("strength") or ""))
    if num:
        same = [m for m in matches if re.search(rf"(?<![\d.]){re.escape(num[0])}\s*(MG|MCG|UNT|ML)", m["rxnorm_name"])]
        brand = str(fields.get("drug_name") or "").split()[0].lower()
        branded = [m for m in same if f"[{brand}" in m["rxnorm_name"].lower()]
        matches = branded or same or matches
    confirm = [k for k, v in checks.items() if v is False]
    if qty is None:
        confirm.append("qty_per_30d")
    if len(matches) != 1:
        confirm.append("which_rxnorm_match")
    return {"label": {k: fields.get(k) for k in ("drug_name", "strength", "dose_form", "directions", "quantity",
                                                  "quantity_unit", "days_supply", "refills", "pharmacy_name", "fill_date")},
            "qty_per_30d": qty, "qty_per_30d_basis": how,
            "rxnorm_matches": [{**m, "display_name": friendly_name(m["rxnorm_name"])} for m in matches],
            "checks": checks, "needs_user_confirmation": confirm}


if __name__ == "__main__":
    print(json.dumps(analyze(sys.argv[1]), indent=1, default=str))
