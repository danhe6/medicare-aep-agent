"""Agent-level eval: does the agent pick the right tools, in the right order, with grounded arguments,
and never state a number that no tool returned? Calls the real agent (Nebius API, costs money).

    PYTHONPATH=src python evals/agent/run_agent_eval.py [--set dev|heldout] [--only d01_full_info] [--repeats 1]

After each scripted user turn, if the agent asks a question, a simulated user (cheap model) answers it from the
scenario's "facts" plus DEFAULT_FACTS, at most "max_followups" times (default 2), so runs don't stall on follow-ups.

Guardrails (any failure fails the run): grounding ($ % stars), dose grounding (mg/units/mL), drug-name grounding,
plan keys, tables, and the scenario's own expectations. North-stars (reported only): questions per reply, tool calls, seconds.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from agent.agent import SYSTEM, run_turn_events  # noqa: E402
from agent.llm import MODELS, NO_THINK, client  # noqa: E402
from grounding import classify, normalize  # noqa: E402

PLAN_KEY = re.compile(r"\bH\d{4}-\d{3}-\d{3}\b")
INFRA_ERROR = re.compile(r"Error code: (402|429|5\d\d)|APIConnectionError|APITimeoutError|RateLimitError")
BUDGET_ERROR = re.compile(r"Error code: 402|exhausted your budget|insufficient", re.I)
TABLE = re.compile(r"^\s*\|.*\|\s*$\n^\s*\|?\s*:?-{3,}", re.M)
Q_LIMIT = {"family": 2, "senior": 1}
from agent.agent import ASKS_LOCATION, RECONFIRM, gave_county  # noqa: E402  same patterns the agent repairs
DEFAULT_FACTS = ("No Medicaid. No hospital stays in the past year. No other prescription medicines. "
                 "Uses a regular retail pharmacy. No doctor preferences unless stated in the conversation.")
SIM_PROMPT = """You are role-playing the person chatting with a Medicare helper, in a test.
FACTS (the only things you know): {facts}
Answer the helper's latest question(s) from the FACTS. For anything the FACTS do not state (a county, a ZIP code,
a medicine, a doctor, an amount), say "I don't know" - never make it up, even if it seems helpful.
If the helper offers something (a phone number, a link), say "yes please". Reply in 1-2 short plain sentences.
Everything under "What I already said" is true: never contradict it or say you are unsure about it.
Do not ask questions and do not add new requests."""


def arg_has(obj, key: str, want) -> bool:
    """key anywhere in the args (also inside drugs[]); strings match as case-insensitive substrings
    ('bill_02' in 'uploads/eval/bill_02.jpg'), numbers within 0.5."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                if isinstance(want, str) and isinstance(v, str) and want.lower() in v.lower():
                    return True
                if isinstance(want, (int, float)) and isinstance(v, (int, float)) and not isinstance(v, bool) \
                        and abs(v - want) <= 0.5:
                    return True
                if v == want:
                    return True
            if arg_has(v, key, want):
                return True
    elif isinstance(obj, list):
        return any(arg_has(x, key, want) for x in obj)
    return False


def simulate_user(llm, facts: str, reply: str) -> str:
    resp = llm.chat.completions.create(model=MODELS["agent"], temperature=0, max_tokens=400,
                                       messages=[{"role": "system", "content": SIM_PROMPT.format(facts=facts)},
                                                 {"role": "user", "content": "The helper said:\n" + reply}])
    return (resp.choices[0].message.content or "I don't know.").strip()


def run_scenario(sc: dict, llm) -> dict:
    for name, src in (sc.get("files") or {}).items():
        dest = ROOT / "uploads" / "eval" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / src, dest)
    messages = [{"role": "system", "content": SYSTEM}]
    turns, t0 = [], time.time()
    facts = " ".join(["What I already said: " + " / ".join(sc["turns"]) + ".", sc.get("facts", ""), DEFAULT_FACTS])
    names: dict = {}
    results: list = []

    def one_turn(user: str, simulated: bool) -> str:
        messages.append({"role": "user", "content": user})
        calls, text = [], ""
        for ev in run_turn_events(messages, llm, lang=sc.get("lang", "en"), mode=sc.get("mode")):
            if ev["type"] == "tool_start":
                calls.append({"name": ev["name"], "args": ev["args"]})
            elif ev["type"] == "tool_done" and not ev["ok"]:
                calls[-1]["error"] = ev["error"]
            elif ev["type"] == "message":
                text = ev["text"]
        names.update({tc["id"]: tc["function"]["name"] for m in messages if m.get("tool_calls") for tc in m["tool_calls"]})
        results[:] = [(names.get(m.get("tool_call_id"), "?"), m["content"]) for m in messages if m.get("role") == "tool"]
        context = [json.dumps(c.get("args", {})) for t in turns for c in t["calls"]] + \
                  [json.dumps(c.get("args", {})) for c in calls] + [r for _, r in results]
        turns.append({"user": user, "calls": calls, "reply": text, "context": context, "simulated": simulated})
        return text

    for user in sc["turns"]:
        text = one_turn(user, False)
        # The scripted turns cannot answer follow-up questions; a simulated user answers from the scenario's facts
        # (at most twice) before the next scripted turn, so a test is not stuck on "Do you have Medicaid?".
        for _ in range(sc.get("max_followups", 2)):
            if "?" not in normalize(text):
                break
            text = one_turn(simulate_user(llm, facts, text), True)
    return {"turns": turns, "results": results, "secs": round(time.time() - t0, 1)}


def check(sc: dict, run: dict) -> dict:
    exp, turns = sc.get("expect", {}), run["turns"]
    all_calls = [c for t in turns for c in t["calls"]]
    blocked = [c for c in all_calls if str(c.get("error", "")).startswith("Not run:")]  # stopped by agent.guard()
    calls = [c for c in all_calls if c not in blocked]
    names = [c["name"] for c in calls]
    replies = [normalize(t["reply"]) for t in turns]
    users = [t["user"] for t in turns]
    g: dict[str, tuple[bool, str]] = {}

    # 1. Every $, %, star rating in a reply comes from a tool (args or result) or from the user.
    ungrounded, doses = [], []
    for t in turns:  # only tool output that existed when this reply was written
        for c in classify(t["reply"], t["context"], users):
            if c["category"] == "UNGROUNDED":
                (doses if c["kind"] == "dose" else ungrounded).append(c["text"])
    g["grounding"] = (not ungrounded, ", ".join(ungrounded))      # $, %, stars: the README promise
    g["dose_grounding"] = (not doses, ", ".join(doses))           # mg / units / mL the user never said

    # 2. Drug names passed to the engine came from find_drug / read_medicine_label results, never typed by the model.
    lookups = " ".join(r for n, r in run["results"] if n in ("find_drug", "read_medicine_label", "update_profile"))
    bad = [d.get("rxnorm_name") for c in calls if c["name"] in ("compare_plans", "check_current_plan")
           for d in c["args"].get("drugs", []) if d.get("rxnorm_name") and json.dumps(d["rxnorm_name"]) not in lookups]
    g["drug_names_from_lookup"] = (not bad, ", ".join(map(str, bad)))

    # 3-4. Style rules from the system prompt that code can check.
    keys = [k for r in replies for k in PLAN_KEY.findall(r)]
    g["no_internal_plan_keys"] = (not keys, ", ".join(keys))
    g["no_tables"] = (not any(TABLE.search(r) for r in replies), "")

    # Scenario expectations.
    for n in exp.get("must_call", []):
        g[f"calls {n}"] = (n in names, "")
    for n in exp.get("must_not_call", []):
        g[f"never calls {n}"] = (n not in names, "")
    for a, b in exp.get("before", []):
        ok = b not in names or (a in names and names.index(a) < names.index(b))
        g[f"{a} before {b}"] = (ok, " > ".join(names))
    for n, k in exp.get("min_calls", {}).items():
        g[f"{n} x{k}+"] = (names.count(n) >= k, f"{names.count(n)} calls")
    for n, kv in exp.get("args_contain", {}).items():
        ok = any(c["name"] == n and all(arg_has(c["args"], k, v) for k, v in kv.items()) for c in calls)
        g[f"{n} args {kv}"] = (ok, "")
    if exp.get("ask_first"):
        first = turns[0]
        ok = "?" in first["reply"] and not any(c["name"] in ("compare_plans", "check_current_plan") for c in first["calls"])
        g["asks before comparing"] = (ok, first["reply"][:120])
    for pat in exp.get("reply_must_mention", []):
        g[f"mentions /{pat}/"] = (any(re.search(pat, r, re.I) for r in replies), "")
    for pat in exp.get("reply_must_not", []):
        hit = [m.group() for r in replies for m in re.finditer(pat, r, re.I)]
        g[f"never says /{pat}/"] = (not hit, ", ".join(hit))

    limit = Q_LIMIT.get(sc.get("mode"), 2)
    q = [r.count("?") for r in replies]
    reconfirm = sum(bool(RECONFIRM.search(r)) for r in replies)  # prompt: never ask to confirm what the user just said
    asked_location = sum(bool(ASKS_LOCATION.search(r)) and gave_county([{"role": "user", "content": t["user"]} for t in turns[:i + 1]])
                         for i, r in enumerate(replies))
    north = {"max_questions_in_a_reply": max(q or [0]), "question_limit": limit,
             "questions_ok": max(q or [0]) <= limit, "reconfirm_asks": reconfirm, "asked_known_location": asked_location, "tool_calls": len(calls),
             "tool_errors": sum(1 for c in calls if c.get("error")), "guard_blocks": len(blocked), "secs": run["secs"]}
    return {"guardrails": {k: {"ok": v[0], "detail": v[1]} for k, v in g.items()},
            "passed": all(v[0] for v in g.values()), "north_star": north}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--only")
    ap.add_argument("--repeats", type=int, default=1)
    a = ap.parse_args()
    scenarios = [json.loads(l) for l in open(HERE / f"scenarios_{a.set}.jsonl") if l.strip()]
    if a.only:
        want = {x.strip() for x in a.only.split(",")}  # ids or id prefixes: --only k01,k04_dual
        scenarios = [s for s in scenarios if any(s["id"] == w or s["id"].startswith(w) for w in want)]
    llm, results, infra = client(), [], []
    for sc in scenarios:
        for r in range(a.repeats):
            try:
                run = run_scenario(sc, llm)
                res = check(sc, run)
            except Exception as e:
                if INFRA_ERROR.search(repr(e)):  # out of credit / rate limit / API down: not the agent's fault
                    infra.append(f"{sc['id']} #{r}")
                    print(f"INFRA {sc['id']} #{r}  {repr(e)[:160]}")
                    if BUDGET_ERROR.search(repr(e)):
                        print("API budget exhausted - stopping. Add funds and re-run with --only for the rest.")
                        break
                    continue
                # any other crash is a failed run, not a broken eval
                run, res = {"turns": [], "results": []}, {"guardrails": {"crashed": {"ok": False, "detail": repr(e)[:300]}},
                                           "passed": False, "north_star": {}}
            results.append({"id": sc["id"], "tags": sc.get("tags", []), "repeat": r, **res,
                            "turns": [{k: v for k, v in t.items() if k != "context"} for t in run["turns"]]})
            mark = "PASS" if res["passed"] else "FAIL"
            fails = [k + (f" ({v['detail']})" if v["detail"] else "") for k, v in res["guardrails"].items() if not v["ok"]]
            print(f"{mark} {sc['id']} #{r}  {res['north_star'].get('secs', '-')}s  " + "; ".join(fails))
        else:
            continue
        break  # budget exhausted
    by_check = collections.defaultdict(lambda: [0, 0])
    for r in results:
        for k, v in r["guardrails"].items():
            by_check[k.split(" ")[0] if k.startswith(("calls", "never", "mentions")) else k][0] += v["ok"]
            by_check[k.split(" ")[0] if k.startswith(("calls", "never", "mentions")) else k][1] += 1
    runs_ok = sum(r["passed"] for r in results)
    print(f"\nRun-level pass rate: {runs_ok}/{len(results)} (gate on this, not on single checks)")
    if infra:
        print(f"  NOT COUNTED: {len(infra)} runs hit API errors (credit / rate limit), re-run them: {', '.join(infra[:6])}"
              + (" ..." if len(infra) > 6 else ""))
    if len(results) + len(infra) < len(scenarios) * a.repeats:
        print("  INCOMPLETE: stopped early, this is not a full-set result")
    for k, (ok, n) in sorted(by_check.items()):
        print(f"  {k:32} {ok}/{n}")
    q_ok = sum(r["north_star"].get("questions_ok", False) for r in results)
    print(f"North-star: question limit kept in {q_ok}/{len(results)} runs; "
          f"asked to re-confirm known facts in {sum(r['north_star'].get('reconfirm_asks', 0) > 0 for r in results)}/{len(results)} runs; "
          f"asked for a location already given in {sum(r['north_star'].get('asked_known_location', 0) > 0 for r in results)}/{len(results)} runs; "
          f"guard blocked a call in {sum(r['north_star'].get('guard_blocks', 0) > 0 for r in results)}/{len(results)} runs")
    complete = not a.only and not infra and len(results) == len(scenarios) * a.repeats
    # only a full, clean run may replace the baseline file; partial / --only / API-error runs go to a side file
    out = HERE / f"results_{a.set}_{'latest' if complete else 'partial'}.json"
    out.write_text(json.dumps({"date": time.strftime("%Y-%m-%d"), "set": a.set, "only": a.only, "infra": infra, "results": results}, indent=1))
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
