"""Summarize logs/metrics.jsonl: runs, calls per task, latency, tokens, cost per chat turn.

    python pipeline/metrics_report.py
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "metrics.jsonl"
PRICES = json.loads((Path(__file__).parent / "model_prices.json").read_text())

recs = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()] if LOG.exists() else []
if not recs:
    raise SystemExit("no metrics yet: chat with the app first")

by_task = defaultdict(list)
runs = defaultdict(lambda: {"cost": 0.0, "priced": True, "tokens": 0, "ms": 0})
for r in recs:
    by_task[(r["task"], r.get("version", ""))].append(r)
    run = runs[r.get("run")]
    run["ms"] += r.get("latency_ms") or 0
    if r["kind"] == "llm":
        pt, ct = r.get("prompt_tokens") or 0, r.get("completion_tokens") or 0
        run["tokens"] += pt + ct
        p = PRICES.get(r.get("model") or "", {})
        if p.get("input") is None or p.get("output") is None:
            run["priced"] = False
        else:
            run["cost"] += pt / 1e6 * p["input"] + ct / 1e6 * p["output"]

print(f"{len(recs):,} logged calls, {len(runs):,} chat turns, {recs[0]['t']} .. {recs[-1]['t']}\n")
print(f"{'task':28} {'ver':4} {'calls':>6} {'ok %':>6} {'p50 ms':>8} {'avg tokens':>11}")
for (task, ver), rs in sorted(by_task.items()):
    ok = 100 * sum(1 for r in rs if r.get("ok")) / len(rs)
    p50 = statistics.median(r.get("latency_ms") or 0 for r in rs)
    toks = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in rs if r["kind"] == "llm"]
    avg = f"{statistics.mean(toks):,.0f}" if toks else "-"
    print(f"{task:28} {ver:4} {len(rs):>6} {ok:>6.1f} {p50:>8,.0f} {avg:>11}")

turns = [v for k, v in runs.items() if k]
print(f"\nper chat turn: median {statistics.median(t['tokens'] for t in turns):,.0f} tokens, "
      f"median {statistics.median(t['ms'] for t in turns) / 1000:,.1f} s")
priced = [t["cost"] for t in turns if t["priced"]]
if priced:
    print(f"cost per chat turn: median ${statistics.median(priced):.4f}, total ${sum(priced):.2f} "
          f"({len(priced)} of {len(turns)} turns priced)")
else:
    print("cost: fill in pipeline/model_prices.json (Nebius Token Factory prices) to compute")
