"""Score the letter reader on the fictional eval set (evals/letters/set, answers in truth.jsonl).

    PYTHONPATH=src python evals/letters/run_eval.py            # all 41 letters, ~2-3 min, about 10 cents
    PYTHONPATH=src python evals/letters/run_eval.py partd_     # only ids starting with partd_

Checks per letter: the type, the deadline (computed by code from the date it read), the key item (drug, service,
plan ID) and the phone number. Writes evals/letters/results_latest.json and prints a table.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from agent.llm import MODELS, client  # noqa: E402
from letters.read import analyze  # noqa: E402

TODAY = date(2026, 10, 12)


def score(row: dict, llm) -> dict:
    t0 = time.perf_counter()
    try:
        out = analyze(str(HERE / row["file"]), today=TODAY, llm=llm)
        err = None
    except Exception as e:  # noqa: BLE001
        out, err = {}, f"{type(e).__name__}: {str(e)[:200]}"
    secs = round(time.perf_counter() - t0, 1)
    got_type = out.get("letter_type")
    blob = json.dumps(out, default=str)
    res = {"id": row["id"], "style": row["style"], "type": row["type"], "got_type": got_type,
           "type_ok": got_type == row["type"], "secs": secs, "error": err}
    if row["type"] == "nomnc":
        got = (out.get("appeal") or {}).get("effective_date") or (out.get("fields") or {}).get("effective_date")
        res.update(want=row["effective_date"], got=got, date_ok=got == row["effective_date"])  # None = must ask
    elif row.get("deadline"):
        got = (out.get("deadline") or {}).get("date")
        res.update(want=row["deadline"], got=got, date_ok=got == row["deadline"])
    if row.get("keyword"):
        res["keyword_ok"] = row["keyword"].lower() in blob.lower()
    if row.get("phone"):
        res["phone_ok"] = row["phone"] in re.sub(r"\D", "", blob)
    return res


def main() -> None:
    rows = [json.loads(x) for x in (HERE / "truth.jsonl").read_text().splitlines() if x.strip()]
    if len(sys.argv) > 1:
        rows = [r for r in rows if r["id"].startswith(sys.argv[1])]
    llm = client()
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda r: score(r, llm), rows))
    by = defaultdict(list)
    for r in results:
        by[r["type"]].append(r)

    def rate(rs, k):
        xs = [r[k] for r in rs if k in r]
        return f"{sum(xs)}/{len(xs)}" if xs else "-"
    print(f"{'type':14} {'n':>3} {'type':>7} {'date':>7} {'item':>7} {'phone':>7}")
    for t, rs in by.items():
        print(f"{t:14} {len(rs):>3} {rate(rs, 'type_ok'):>7} {rate(rs, 'date_ok'):>7} {rate(rs, 'keyword_ok'):>7} {rate(rs, 'phone_ok'):>7}")
    print(f"{'ALL':14} {len(results):>3} {rate(results, 'type_ok'):>7} {rate(results, 'date_ok'):>7} "
          f"{rate(results, 'keyword_ok'):>7} {rate(results, 'phone_ok'):>7}")
    print("vision model:", MODELS["vision"])
    print("median seconds per letter:", sorted(r["secs"] for r in results)[len(results) // 2])
    for r in results:
        if not r["type_ok"] or r.get("date_ok") is False or r.get("error"):
            print("MISS", r["id"], r["style"], "type", r["type"], "->", r["got_type"], "| date", r.get("want"), "->", r.get("got"), r.get("error") or "")
    tag = MODELS["vision"].split("/")[-1]
    payload = json.dumps({"today": TODAY.isoformat(), "vision_model": MODELS["vision"], "results": results}, indent=1)
    (HERE / "results_latest.json").write_text(payload)
    (HERE / f"results_{tag}.json").write_text(payload)  # one file per vision model, for A/B


if __name__ == "__main__":
    main()
