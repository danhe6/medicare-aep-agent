"""The evaluator for drafted letters: plain code, not another model (cheap, predictable, testable)."""
from __future__ import annotations

import json
import re

CLAIMS = re.compile(r"\bI\s+(?:have\s+|had\s+|previously\s+|already\s+|also\s+)*(?:tried|took|taken|attempted|"
                    r"experienced|suffered|developed|failed|was hospitali[sz]ed|could not tolerate|cannot tolerate)\b|"
                    r"\bmy\s+(?:doctor|prescriber|physician)\s+(?:has\s+)?(?:determined|found|confirmed|documented)\b|"
                    r"\b(?:as\s+)?(?:documented|confirmed|verified)\s+by\b|\bmy\s+(?:current\s+)?(?:functional\s+limitations|diagnosis|symptoms)\b", re.I)
BANNED = re.compile(r"\b(guarantee|will be approved|must approve|lawsuit|sue)\b", re.I)


def check_draft(par: str, facts: dict) -> list[str]:
    """Evaluator (code, not a model): every number in the paragraph must come from the facts; no promises."""
    problems = []
    num = r"\d+(?:[.,]\d+)*"
    allowed = {re.sub(r"\D", "", n) for n in re.findall(num, json.dumps(facts))}
    for n in re.findall(num, re.sub(r"\[[^\]]*\]", "", par)):
        if re.sub(r"\D", "", n) not in allowed:
            problems.append(f"number not in facts: {n}")
    outside = re.sub(r"\[[^\]]*\]", "", par)
    if CLAIMS.search(outside):  # personal medical history is the person's to state, never the model's
        problems.append("states medical history that is not in the facts (use a [placeholder] instead)")
    if BANNED.search(par):
        problems.append("promises an outcome")
    if len(par) > 1200:
        problems.append("too long")
    return problems




STATED_DAYS = re.compile(r"(?:within|have|has)\s+(\d{2,3})\s+(?:calendar\s+)?days\s+(?:from|of|after)\s+the\s+date", re.I)


def stated_days(text: str) -> int | None:
    """The appeal window the letter itself prints ("You have 60 days from the date of this notice"), if any.
    Older notices print 60 days; current rules give 65. The letter in the person's hands is what they will read."""
    for m in STATED_DAYS.finditer(text or ""):
        n = int(m.group(1))
        if 30 <= n <= 180:
            return n
    return None


KEYWORDS = [  # (type, pattern) - the official notice titles, checked in order
    ("nomnc", r"notice of medicare non-?coverage"),
    ("partd_denial", r"notice of denial of medicare prescription drug coverage|request for redetermination of medicare prescription drug"),
    ("ma_denial", r"notice of denial of medical coverage|integrated denial notice|notice of denial of payment"),
    ("msn", r"medicare summary notice"),
    ("irmaa", r"income-?related monthly adjustment|\birmaa\b"),
    ("anoc", r"annual notice of changes?"),
    ("eob", r"explanation of benefits|part d eob"),
    ("bill", r"(?=[\s\S]*\b(?:patient|provider|physician|clinic|hospital|medical|office visit|x-ray|cpt|date of service)\b)"
             r"[\s\S]*(?:amount due|balance due|please pay|pay this amount|patient balance|amount you owe)"),
]


def keyword_type(text: str) -> str | None:
    low = text.lower()
    return next((kind for kind, pat in KEYWORDS if re.search(pat, low)), None)
