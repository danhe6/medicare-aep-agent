"""One table for the README from the latest results of every agent eval set.

Run each set with repeats first (the model is not deterministic, so one run is a sample, not a score):
    for s in dev heldout heldout2 heldout3; do PYTHONPATH=src python evals/agent/run_agent_eval.py --set $s --repeats 3; done
    python evals/agent/summarize.py            # prints a markdown table; --json for machine output
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETS = ["dev", "heldout", "heldout2", "heldout3"]
# guardrails that back a promise in the README, reported on their own
PROMISES = {"grounding": "numbers come from a tool", "dose_grounding": "doses come from the user or a tool",
            "drug_names_from_lookup": "drug names come from RxNorm", "no_internal_plan_keys": "no internal keys shown"}


def load(s: str) -> dict | None:
    f = HERE / f"results_{s}_latest.json"
    return json.loads(f.read_text()) if f.exists() else None


def main() -> None:
    rows, total, promise, flaky = [], [0, 0], collections.defaultdict(lambda: [0, 0]), []
    for s in SETS:
        r = load(s)
        if not r:
            continue
        res = r["results"]
        by_sc = collections.defaultdict(list)
        for x in res:
            by_sc[x["id"]].append(bool(x["passed"]))
            for k, v in x["guardrails"].items():
                if k in PROMISES:
                    promise[k][0] += v["ok"]
                    promise[k][1] += 1
        reps = max(len(v) for v in by_sc.values())
        ok, n = sum(sum(v) for v in by_sc.values()), sum(len(v) for v in by_sc.values())
        all_pass = sum(all(v) for v in by_sc.values())
        flaky += [f"{k} ({sum(v)}/{len(v)})" for k, v in by_sc.items() if 0 < sum(v) < len(v)]
        flaky += [f"{k} (0/{len(v)})" for k, v in by_sc.items() if not any(v)]
        secs = sorted(x["north_star"].get("secs", 0) for x in res if x.get("north_star"))
        rows.append((s, len(by_sc), reps, ok, n, all_pass, secs[len(secs) // 2] if secs else 0, r.get("date", "")))
        total[0] += ok
        total[1] += n
    if "--json" in sys.argv:
        print(json.dumps({"sets": rows, "total": total, "promises": promise, "not_always_passing": flaky}, indent=1))
        return
    print("| Set | Scenarios | Runs each | Runs passed | Scenarios passing every run | Median secs |")
    print("|---|---|---|---|---|---|")
    for s, sc, reps, ok, n, allp, med, _ in rows:
        print(f"| {s} | {sc} | {reps} | {ok}/{n} ({100 * ok / n:.0f}%) | {allp}/{sc} | {med:.0f} |")
    if total[1]:
        print(f"| **all** | | | **{total[0]}/{total[1]} ({100 * total[0] / total[1]:.0f}%)** | | |")
    print("\n| Promise (checked in every reply) | Held |\n|---|---|")
    for k, (ok, n) in promise.items():
        print(f"| {PROMISES[k]} | {ok}/{n} |")
    if flaky:
        print("\nNot passing every run: " + ", ".join(flaky))


if __name__ == "__main__":
    main()
