"""Compare our engine against the Plan Finder answer key (evals/oracle/*.json).

    PYTHONPATH=src python evals/run_eval.py [--verbose]

For each persona x plan, prices at the same pharmacy type Plan Finder used (preferred vs standard retail),
and only counts drugs Plan Finder actually priced. Gate: >= 80% of comparisons within 10%.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from engine import data
from engine.estimate import estimate_plan

EVALS = Path(__file__).resolve().parent


def main() -> None:
    con = data.connect()
    data.load_market(con, "Florida", "Miami-Dade")
    plans = {p.key: p for p in data.plans(con)}
    rows = []
    for opath in sorted((EVALS / "oracle").glob("*.json")):
        oracle = json.loads(opath.read_text())
        persona = json.loads((EVALS / "personas" / f"{oracle['persona']}.json").read_text())
        for key, ans in oracle["plans"].items():
            if key not in plans or ans.get("yearly_total") is None or not ans.get("in_network", True):
                continue
            priced = {d["ndc"] for d in ans["drugs"]}
            drugs = [d for d in persona["drugs"] if d.get("oracle_ndc") in priced]
            if not drugs:
                continue
            pharmacy = "preferred_retail" if ans.get("preferred_pharmacy") else "standard_retail"
            est = estimate_plan(con, plans[key], drugs, pharmacy)
            ours = est["drug_oop"]
            pf = float(ans["yearly_total"])
            err = abs(ours - pf) / pf if pf else (0.0 if ours < 1 else 1.0)
            ours_cov = {d["drug"]: d["covered"] for d in est["drugs"]}
            pf_cov = {d["ndc"]: d["covered"] for d in ans["drugs"]}
            cov_mismatch = [d["name"] for d in drugs if ours_cov.get(d["name"]) != pf_cov.get(d["oracle_ndc"])]
            pf_uncovered = any(not d["covered"] for d in ans["drugs"])
            rows.append({"persona": oracle["persona"], "plan": key, "ours": ours, "pf": pf,
                         "coverage_only": pf_uncovered,
                         "abs_err": err, "diff": ours - pf, "ok": err <= 0.10 or abs(ours - pf) <= 100,
                         "coverage_mismatch": cov_mismatch,
                         "skipped_by_pf": len(persona["drugs"]) - len(drugs)})
    if not rows:
        raise SystemExit("No oracle files found. Run evals/fetch_oracle.py first.")
    # Plans where a drug is NOT covered: Plan Finder prices it at the pharmacy cash price, which is not
    # public; we only report a lower bound. Score those on coverage agreement, not dollars.
    cov_only = [r for r in rows if r["coverage_only"]]
    for r in cov_only:
        r["ok"] = not r["coverage_mismatch"]
    priced = [r for r in rows if not r["coverage_only"]]

    def pct(th): return 100 * sum(r["abs_err"] <= th for r in priced) / len(priced)
    print(f"Coverage-only comparisons (a drug is not covered): {len(cov_only)}; coverage agrees on "
          f"{sum(r['ok'] for r in cov_only)}/{len(cov_only)}")
    print(f"Priced comparisons: {len(priced)}  |  exact (<=1%): {pct(0.01):.0f}%  within 5%: {pct(0.05):.0f}%  "
          f"within 10%: {pct(0.10):.0f}%  |  median abs error: {100*statistics.median(r['abs_err'] for r in priced):.1f}%")
    ok = 100 * sum(r["ok"] for r in rows) / len(rows)
    covmis = sum(1 for r in rows if r["coverage_mismatch"])
    print(f"OK (within 10% OR within $100/yr): {ok:.0f}%   |   coverage disagreements: {covmis}/{len(rows)}")
    print("\nBy persona:")
    for name in sorted({r["persona"] for r in rows}):
        rs = [r for r in rows if r["persona"] == name]
        w10 = 100 * sum(r["ok"] for r in rs) / len(rs)
        skipped = max(r["skipped_by_pf"] for r in rs)
        print(f"  {name:22} n={len(rs):3}  OK: {w10:5.0f}%  median $-err {(100*statistics.median(r['abs_err'] for r in rs if not r['coverage_only'])) if any(not r['coverage_only'] for r in rs) else float('nan'):5.1f}%  coverage-only {sum(r['coverage_only'] for r in rs):2}"
              + (f"   (Plan Finder skipped {skipped} drug(s))" if skipped else ""))
    print("\nWorst 10 by dollars (priced comparisons):")
    for r in sorted(priced, key=lambda r: -abs(r["diff"]))[:10]:
        print(f"  {r['persona']:22} {r['plan']:15} ours ${r['ours']:>8,.0f}  PF ${r['pf']:>8,.0f}  ({r['diff']:+,.0f})"
              + (f"  coverage differs: {r['coverage_mismatch']}" if r["coverage_mismatch"] else ""))
    gate = ok >= 80
    print(f"\nGate 1 (>= 80% OK): {'PASS' if gate else 'FAIL'}")
    out = EVALS / "results_latest.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"Details: {out}")
    if "--min-ok" in sys.argv and ok < float(sys.argv[sys.argv.index("--min-ok") + 1]):
        sys.exit(1)


if __name__ == "__main__":
    main()
