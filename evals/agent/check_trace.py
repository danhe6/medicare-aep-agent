"""Rung 0, free: run the number-grounding check on conversations already in logs/agent_trace.jsonl (no API calls).

    python evals/agent/check_trace.py [--show]

The trace has no conversation ids, so a conversation = events until a gap of more than 15 minutes.
User messages are not in the trace, so numbers the user typed can show up as UNGROUNDED: review those by hand.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grounding import classify  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def secs(t: str) -> int:
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def main() -> None:
    show = "--show" in sys.argv
    events = [json.loads(l) for l in open(ROOT / "logs" / "agent_trace.jsonl")]
    convo, last, n_conv = [], None, 0
    tally, bad = collections.Counter(), []
    for e in events:
        t = secs(e["t"])
        if last is not None and (t - last > 900 or t < last):
            convo, n_conv = [], n_conv + 1
        last = t
        if "tool" in e:
            convo.append((e.get("args") or "") + " " + (e.get("result") or ""))  # args = what the user told the model
            continue
        reply = e.get("assistant") or ""
        for c in classify(reply, convo):
            tally[(c["kind"], c["category"])] += 1
            if c["category"] in ("UNGROUNDED", "derived") and show or c["category"] == "UNGROUNDED":
                bad.append({"cat": c["category"], "conv": n_conv, "t": e["t"], "claim": c["text"],
                            "context": reply[max(0, c["start"] - 80): c["start"] + 60].replace("\n", " ")})
    replies = sum(1 for e in events if "assistant" in e)
    total = sum(tally.values())
    print(f"conversations ~{n_conv + 1}, replies {replies}, numeric claims {total}")
    for k in sorted(tally):
        print(f"  {k[0]:6} {k[1]:11} {tally[k]}")
    print(f"UNGROUNDED: {sum(b['cat'] == 'UNGROUNDED' for b in bad)}  (guardrail: 0)")
    for b in bad[: (len(bad) if show else 15)]:
        print(f"  {b['cat']:10} [conv {b['conv']} {b['t']}] {b['claim']!r}: ...{b['context']}...")


if __name__ == "__main__":
    main()
