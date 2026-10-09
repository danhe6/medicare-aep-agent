"""Bill vs EOB / MSN: two photos -> lines read by Lightning -> billcheck.compare (code) -> verdict + call script."""
from __future__ import annotations

from pathlib import Path

from agent.llm import MODELS, NO_THINK, client
from defend.notice import _json, transcribe
from letters.billcheck import call_script, compare
from letters.checks import keyword_type

BILL = ('{"provider_name", "statement_date", "amount_due": total the bill asks you to pay, "lines": [{"date": service date, '
        '"description", "amount_due": what this line asks YOU to pay (after insurance, if shown)}]}')
STMT = ('{"plan_name", "lines": [{"date": service date, "provider", "description", "you_owe": the amount YOU may be billed '
        '(patient responsibility / your share / maximum you may be billed)}]}')


def _read(text: str, keys: str, llm) -> dict:
    resp = llm.chat.completions.create(model=MODELS["extract"], temperature=0, max_tokens=2500, extra_body=NO_THINK, messages=[{
        "role": "user", "content": f"Return ONLY a JSON object with keys {keys}. Copy dates and dollar amounts exactly as printed; "
                                   f"null if not printed.\n\nDocument:\n{text[:12000]}"}])
    return _json(resp.choices[0].message.content)


def analyze(bill_path: str, statement_path: str, lang: str = "en", llm=None) -> dict:
    llm = llm or client()
    from agent import metrics
    with metrics.task("letter.transcribe"):
        bill_text, st_text = transcribe(Path(bill_path), llm), transcribe(Path(statement_path), llm)
    kind = keyword_type(st_text)
    if kind not in ("eob", "msn"):  # maybe the two photos were sent in the other order
        if keyword_type(bill_text) in ("eob", "msn"):
            bill_text, st_text = st_text, bill_text
            kind = keyword_type(st_text)
        else:
            return {"error": "The second photo doesn't look like an Explanation of Benefits or a Medicare Summary Notice. "
                             "Ask the user for the EOB (from the plan) or MSN (from Medicare) that covers the same visit."}
    with metrics.task("bill.extract"):
        bill, stmt = _read(bill_text, BILL, llm), _read(st_text, STMT, llm)
    result = compare(bill, stmt)
    result.update(statement_kind=kind, provider_name=bill.get("provider_name"), statement_date=bill.get("statement_date"),
                  plan_name=stmt.get("plan_name"), call_script=call_script(result, bill, kind, lang))
    return result
