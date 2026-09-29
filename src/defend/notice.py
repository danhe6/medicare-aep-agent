"""Read a care-ending notice (photo, scan or PDF) and turn it into an appeal plan.

    PYTHONPATH=src python -m defend.notice evals/fixtures/nomnc_sample_photo.jpg --now 2026-10-07T18:00

Pipeline: Gemma 3 (vision) transcribes the page -> Nemotron Lightning extracts fields as JSON ->
deterministic checks confirm every date/phone actually appears in the text -> rules.plan_appeal().
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agent.llm import MODELS, client
from defend.rules import plan_appeal

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
PHONE = re.compile(r"1?[-. (]*\d{3}[-. )]*\d{3}[-. ]*\d{4}")


def transcribe(path: Path, llm=None) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # pip install pypdf
        text = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        if len(text.strip()) > 200:
            return text
        raise ValueError("Scanned PDF: send a photo of each page instead")
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text()
    llm = llm or client()
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    resp = llm.chat.completions.create(model=MODELS["vision"], temperature=0, max_tokens=3000, messages=[{
        "role": "user", "content": [
            {"type": "text", "text": "Transcribe ALL text on this document exactly as written, top to bottom. "
                                     "Keep dates, names and phone numbers exactly. Output only the text."},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}])
    return resp.choices[0].message.content or ""


EXTRACT_PROMPT = """From this Medicare notice text, return ONLY a JSON object with these keys (null if not present):
{"notice_type": "NOMNC" | "IM_hospital_discharge" | "other",
 "service": "snf" | "home_health" | "hospice" | "corf" | null,
 "effective_date": "YYYY-MM-DD"  (the date coverage ENDS / last covered day),
 "effective_date_as_written": "exact text of that date as it appears",
 "qio_name": string, "qio_phone": string,
 "plan_name": string, "plan_phone": string,
 "provider_name": string,
 "patient_first_name": string,
 "notice_date": "YYYY-MM-DD" (date signed/received, if shown),
 "medicare_health_plan": true if a Medicare health plan (Medicare Advantage) contact is listed, false if the notice
                         says Original Medicare only, else null}
Notice text:
"""


def _json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    for m in re.finditer(r"\{.*\}", text, re.S):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
    return {}


def _ask(llm, model: str, text: str) -> tuple[dict, str]:
    resp = llm.chat.completions.create(model=model, temperature=0, max_tokens=4000,
                                       messages=[{"role": "user", "content": EXTRACT_PROMPT + text}])
    raw = resp.choices[0].message.content or ""
    return _json(raw), raw


def regex_fields(text: str) -> dict:
    """Deterministic fallback for the standard CMS-10123 wording."""
    out = {}
    m = re.search(r"will\s+end\s*:?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if m:
        out["effective_date_as_written"] = m.group(1).strip()
    m = re.search(r"call\s+your\s+QIO\s+at\s*:?\s*(.+?)\s+(1?[-. (]*\d{3}[-. )]*\d{3}[-. ]*\d{4})", text, re.I | re.S)
    if m:
        out["qio_name"], out["qio_phone"] = " ".join(m.group(1).split()), m.group(2).strip()
    m = re.search(r"current\s+(skilled nursing|home health|hospice|comprehensive outpatient)", text, re.I)
    if m:
        out["service"] = {"skilled nursing": "snf", "home health": "home_health", "hospice": "hospice",
                          "comprehensive outpatient": "corf"}[m.group(1).lower()]
    if re.search(r"notice of medicare non-coverage", text, re.I):
        out["notice_type"] = "NOMNC"
    return out


def extract(text: str, llm=None) -> dict:
    """LLM extraction (Lightning, then Super), with regex fallback for the critical fields. Records sources."""
    llm = llm or client()
    fields, source = {}, {}
    for role in ("extract", "agent"):
        got, _raw = _ask(llm, MODELS[role], text)
        if got.get("effective_date"):
            fields, src = got, MODELS[role]
            source = {k: src for k, v in got.items() if v not in (None, "")}
            break
    for k, v in regex_fields(text).items():
        if not fields.get(k):
            fields[k] = v
            source[k] = "regex"
    if not fields.get("effective_date") and fields.get("effective_date_as_written"):
        d = _parse_date(fields["effective_date_as_written"])
        fields["effective_date"] = d.isoformat() if d else None
        source["effective_date"] = "regex"
    fields["_source"] = source
    return fields


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.search(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower()[:3] in {k[:3] for k in MONTHS}:
        mon = next(v for k, v in MONTHS.items() if k.startswith(m.group(1).lower()[:3]))
        return date(int(m.group(3)), mon, int(m.group(2)))
    return None


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")[-10:]


# Medicare has two BFCC-QIOs nationwide; OCR often garbles their names ("Acenta", "Liventa").
KNOWN_QIOS = ["Acentra Health", "Livanta"]


def normalize_qio(name: str | None) -> str | None:
    if not name:
        return name
    import difflib
    first = name.split()[0].lower()
    for q in KNOWN_QIOS:
        if difflib.SequenceMatcher(None, first, q.split()[0].lower()).ratio() >= 0.75:
            return q
    return name


def verify(fields: dict, text: str) -> dict:
    """Every critical value must be traceable to the transcribed text; otherwise ask the user to confirm."""
    checks = {}
    eff = _parse_date(fields.get("effective_date"))
    written = fields.get("effective_date_as_written") or ""
    checks["effective_date_found_in_text"] = bool(eff and written and written.lower() in text.lower()
                                                  and _parse_date(written) == eff)
    phones = {_digits(p) for p in PHONE.findall(text)}
    checks["qio_phone_found_in_text"] = bool(fields.get("qio_phone")) and _digits(fields["qio_phone"]) in phones
    checks["needs_user_confirmation"] = [k for k, v in checks.items() if not v]
    return checks


def analyze(path: str, now: datetime | None = None, tz: str = "America/New_York",
            medicare_advantage: bool | None = None, llm=None, lang: str = "en") -> dict:
    llm = llm or client()
    from agent import metrics
    with metrics.task("notice.transcribe"):
        text = transcribe(Path(path), llm)
    with metrics.task("notice.extract"):
        fields = extract(text, llm)
    fields["qio_name"] = normalize_qio(fields.get("qio_name"))
    checks = verify(fields, text)
    if fields.get("provider_name"):   # names can't be checked against a list: ask the user to glance at it
        checks["needs_user_confirmation"].append("provider_name")
    eff = _parse_date(fields.get("effective_date"))
    out = {"fields": fields, "checks": checks, "transcript_chars": len(text)}
    if fields.get("notice_type") not in (None, "NOMNC"):
        out["note"] = f"This looks like a {fields.get('notice_type')} notice; only NOMNC is supported so far."
    if not eff:
        out["error"] = "Could not read the date coverage ends. Ask the user to type it from the notice."
        return out
    ma = medicare_advantage if medicare_advantage is not None else bool(fields.get("medicare_health_plan"))
    out["appeal"] = plan_appeal(
        eff, now or datetime.now(ZoneInfo(tz)), service=fields.get("service") or "snf", medicare_advantage=ma,
        notice_received=_parse_date(fields.get("notice_date")), qio_name=fields.get("qio_name"),
        qio_phone=fields.get("qio_phone"), provider=fields.get("provider_name"),
        patient_first_name=fields.get("patient_first_name"), tz=tz, lang=lang).to_dict()
    return out


if __name__ == "__main__":
    now = None
    if "--now" in sys.argv:
        now = datetime.fromisoformat(sys.argv[sys.argv.index("--now") + 1]).replace(tzinfo=ZoneInfo("America/New_York"))
    print(json.dumps(analyze(sys.argv[1], now=now), indent=1, default=str))
