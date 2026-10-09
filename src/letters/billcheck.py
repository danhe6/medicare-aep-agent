"""Compare a provider's bill with the plan's EOB (or Medicare's MSN) for the same visits. Plain code, no LLM.

Rule of thumb we apply (and say): for covered services, what you owe is the amount the EOB/MSN shows as your share
("patient responsibility", "you may be billed", "maximum you may be billed"). A bill asking for more than that is
worth a phone call before paying. In Medicare Advantage, in-network providers can't charge more than the plan's
cost sharing; in Original Medicare, a participating provider can't bill more than the MSN amount.
"""
from __future__ import annotations

import difflib
import re
from datetime import date


def money(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    m = re.search(r"-?\d[\d,]*(?:\.\d{1,2})?", str(v))
    return round(float(m.group(0).replace(",", "")), 2) if m else None


def _day(v) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s[:10]
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return date(y, int(m.group(1)), int(m.group(2))).isoformat()
    return None


def _similar(a: str | None, b: str | None) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def compare(bill: dict, statement: dict) -> dict:
    """bill: {lines: [{date, description, amount_due}], amount_due}; statement: {lines: [{date, description, you_owe}]}.
    Returns per-line results and an overall verdict: 'ok' | 'overbilled' | 'unmatched' (bill line not on the statement)."""
    st_lines = [dict(x, _day=_day(x.get("date")), _owe=money(x.get("you_owe"))) for x in statement.get("lines") or []]
    used, rows = set(), []
    for b in bill.get("lines") or []:
        bday, bdue = _day(b.get("date")), money(b.get("amount_due"))
        cands = [(i, s) for i, s in enumerate(st_lines) if i not in used and (not bday or not s["_day"] or s["_day"] == bday)]
        best = max(cands, key=lambda c: _similar(b.get("description"), c[1].get("description")), default=None)
        if not best:
            rows.append({"date": bday, "description": b.get("description"), "billed": bdue, "you_owe": None, "status": "unmatched"})
            continue
        used.add(best[0])
        owe = best[1]["_owe"]
        diff = round(bdue - owe, 2) if bdue is not None and owe is not None else None
        rows.append({"date": bday, "description": b.get("description"), "statement_description": best[1].get("description"),
                     "billed": bdue, "you_owe": owe, "difference": diff,
                     "status": "overbilled" if diff is not None and diff > 0.5 else "ok"})
    total_billed = money(bill.get("amount_due"))
    if total_billed is None:
        total_billed = round(sum(r["billed"] or 0 for r in rows), 2)
    total_owe = round(sum(r["you_owe"] or 0 for r in rows if r["status"] != "unmatched"), 2)
    over = round(sum(r["difference"] for r in rows if r["status"] == "overbilled"), 2)
    verdict = "overbilled" if over > 0.5 else "unmatched" if any(r["status"] == "unmatched" for r in rows) else "ok"
    return {"lines": rows, "total_billed": total_billed, "total_you_owe": total_owe, "over_by": over, "verdict": verdict}


SCRIPT = {
    "en": ("Hi, I'm calling about a bill for {who} dated {bill_date}, account [number on the bill]. For the visit on "
           "{visit}, my {stmt} says I owe {owe}, but the bill asks for {billed}. Could you check the claim and send me a "
           "corrected bill? Please hold the account while you check. Thank you."),
    "es": ("Hola, llamo por una factura de {who} con fecha {bill_date}, cuenta [número en la factura]. Por la visita del "
           "{visit}, mi {stmt} dice que debo {owe}, pero la factura pide {billed}. ¿Pueden revisar el reclamo y enviarme "
           "una factura corregida? Por favor no envíen la cuenta a cobranza mientras lo revisan. Gracias."),
}


def call_script(result: dict, bill: dict, stmt_kind: str, lang: str = "en") -> str | None:
    over = [r for r in result["lines"] if r["status"] == "overbilled"]
    if not over:
        return None
    r = over[0]
    names = {"en": {"eob": "plan's Explanation of Benefits", "msn": "Medicare Summary Notice"},
             "es": {"eob": "Explicación de Beneficios del plan", "msn": "Resumen de Medicare"}}
    lang = lang if lang in SCRIPT else "en"
    from letters.rules import fmt
    visit = fmt(date.fromisoformat(r["date"]), lang) if r["date"] else "[date]"
    who = (bill.get("provider_name") or "[provider]").title() if (bill.get("provider_name") or "").isupper() else (bill.get("provider_name") or "[provider]")
    return SCRIPT[lang].format(who=who, bill_date=bill.get("statement_date") or "[date]",
                               visit=visit, stmt=names[lang].get(stmt_kind, names[lang]["eob"]),
                               owe=f"${r['you_owe']:,.2f}", billed=f"${r['billed']:,.2f}")
