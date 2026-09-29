"""Day 2, step 2: estimate annual Part D cost for one persona across all Miami-Dade plans.

Run from the repo root (after day2_01):
    python3 notebooks/day2_02_spike_cost.py [evals/personas/spike.json] [--year 2026]

Writes:
  data/processed/spike_results.csv   every plan, ranked by estimated drug OOP + premium
  docs/spike_compare.csv             5 plans to check by hand on Medicare.gov Plan Finder
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from engine.part_d_cost import DrugFill, annual_cost  # noqa: E402

DB = ROOT / "data" / "processed" / "partd.duckdb"
CACHE = ROOT / "data" / "processed" / "rxnav_cache.json"
RXNAV = "https://rxnav.nlm.nih.gov/REST"


# ---------- RxNorm: drug name -> RXCUI -> NDCs ----------
def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def rxnorm(name: str, cache: dict) -> dict:
    if name in cache:
        return cache[name]
    q = urllib.parse.quote(name)
    ids = _get(f"{RXNAV}/rxcui.json?name={q}&search=2").get("idGroup", {}).get("rxnormId") or []
    if not ids:
        raise SystemExit(f"RxNorm could not find '{name}'. Use the exact RxNorm name (see rxnav.nlm.nih.gov).")
    rxcui = ids[0]
    ndcs = _get(f"{RXNAV}/rxcui/{rxcui}/ndcs.json").get("ndcGroup", {}).get("ndcList", {}).get("ndc") or []
    cache[name] = {"rxcui": rxcui, "ndcs": ndcs}
    return cache[name]


# ---------- DuckDB helpers ----------
def col(con, table: str, *candidates: str) -> str:
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    for c in candidates:
        if c in cols:
            return c
    raise SystemExit(f"Column not found in {table}. Tried {candidates}. Actual columns: {cols}")


def main() -> None:
    import duckdb

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(sys.argv[sys.argv.index("--year") + 1]) if "--year" in sys.argv else 2026
    persona = json.loads(Path(args[0] if args else ROOT / "evals/personas/spike.json").read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    drugs = []
    for d in persona["drugs"]:
        info = rxnorm(d["name"], cache)
        drugs.append({**d, **info})
        print(f"{d['name']}: RXCUI {info['rxcui']}, {len(info['ndcs'])} NDCs")
    CACHE.write_text(json.dumps(cache, indent=1))

    con = duckdb.connect(str(DB), read_only=True)
    # column names (normalize_names lowercases them)
    f_form = col(con, "formulary", "formulary_id")
    f_rx = col(con, "formulary", "rxcui")
    f_tier = col(con, "formulary", "tier_level_value", "tier_level", "tier")
    f_pa = col(con, "formulary", "prior_authorization_yn")
    f_st = col(con, "formulary", "step_therapy_yn")
    f_ql = col(con, "formulary", "quantity_limit_yn")
    p_ndc = col(con, "pricing", "ndc")
    p_cost = col(con, "pricing", "unit_cost")
    p_days = col(con, "pricing", "days_supply")
    b_lvl = col(con, "bene_cost", "coverage_level")
    b_tier = col(con, "bene_cost", "tier")
    b_days = col(con, "bene_cost", "days_supply")
    # preferred retail first; fall back to standard (non-preferred) retail when the plan has no preferred tier
    b_type = col(con, "bene_cost", "cost_type_pref")
    b_amt = col(con, "bene_cost", "cost_amt_pref")
    b_type_np = col(con, "bene_cost", "cost_type_nonpref")
    b_amt_np = col(con, "bene_cost", "cost_amt_nonpref")
    b_ded = col(con, "bene_cost", "ded_applies_yn")

    plans = con.execute("""
        SELECT DISTINCT contract_id, plan_id, segment_id, plan_name, formulary_id,
               try_cast(premium AS DOUBLE), try_cast(deductible AS DOUBLE)
        FROM miami_plans
    """).fetchall()
    print(f"\nPricing {len(plans)} Miami-Dade plans for {year} ...")

    results = []
    for contract, plan, seg, pname, form_id, premium, deductible in plans:
        fills = []
        for d in drugs:
            f = con.execute(f"""
                SELECT try_cast({f_tier} AS INT), {f_pa}, {f_st}, {f_ql} FROM formulary
                WHERE {f_form} = ? AND {f_rx} = ? ORDER BY 1 LIMIT 1
            """, [form_id, d["rxcui"]]).fetchone()
            if not f:
                fills.append(DrugFill(d["name"], None, d["qty_per_30d"], False))
                continue
            tier, pa, st, ql = f
            flags = [k for k, v in (("PA", pa), ("ST", st), ("QL", ql)) if (v or "").upper() == "Y"]
            costs = [r[0] for r in con.execute(f"""
                SELECT try_cast({p_cost} AS DOUBLE) FROM pricing
                WHERE contract_id = ? AND plan_id = ? AND {p_ndc} IN (SELECT unnest(?::VARCHAR[]))
                  AND {p_days} IN ('30', '1', '030')
            """, [contract, plan, d["ndcs"]]).fetchall() if r[0] is not None]
            unit = statistics.median(costs) if costs else None
            bc = con.execute(f"""
                SELECT {b_type}, try_cast({b_amt} AS DOUBLE), {b_type_np}, try_cast({b_amt_np} AS DOUBLE), {b_ded}
                FROM bene_cost
                WHERE contract_id = ? AND plan_id = ? AND segment_id = ?
                  AND {b_lvl} = '1' AND try_cast({b_tier} AS INT) = ? AND {b_days} = '1'
                LIMIT 1
            """, [contract, plan, seg, tier]).fetchone()
            # COST_TYPE codes: 0 = not offered at this pharmacy type, 1 = copay, 2 = coinsurance
            if bc:
                t_p, a_p, t_np, a_np, ded = bc
                ctype, camt = (t_p, a_p) if str(t_p) in ("1", "2") else (t_np, a_np)
            else:
                ctype, camt, ded = None, None, "Y"
            ctype = {"1": "copay", "2": "coinsurance"}.get(str(ctype), None)
            fills.append(DrugFill(d["name"], unit, d["qty_per_30d"], unit is not None, tier, ctype, camt,
                                  (ded or "Y").upper() == "Y", flags))
        r = annual_cost(f"{contract}-{plan}-{seg}", premium or 0.0, deductible or 0.0, fills, year)
        results.append((r, pname, fills))

    results.sort(key=lambda x: (len(x[0].not_covered), x[0].total))
    out = ROOT / "data/processed/spike_results.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["plan_key", "plan_name", "annual_premium", "drug_oop", "total", "hit_cap_month",
                    "not_covered", "flags", "tiers"])
        for r, pname, fills in results:
            w.writerow([r.plan_key, pname, r.annual_premium, r.drug_oop, r.total, r.hit_cap_month,
                        "; ".join(r.not_covered), json.dumps(r.flags), [f.tier for f in fills]])
    print(f"Wrote {out}")

    print("\nTop 10 (fewest uncovered drugs, then lowest premium + drug cost):")
    for r, pname, _ in results[:10]:
        print(f"  {r.plan_key:18} ${r.total:>8,.0f}  (drugs ${r.drug_oop:,.0f} + premium ${r.annual_premium:,.0f})"
              f"  {pname[:45]}  {'NOT COVERED: ' + ', '.join(r.not_covered) if r.not_covered else ''}")

    # pick 5 plans spread across the ranking for the Plan Finder check
    idx = sorted({0, len(results)//4, len(results)//2, 3*len(results)//4, len(results)-1})
    cmp_path = ROOT / "docs/spike_compare.csv"
    if cmp_path.exists():  # never overwrite a filled-in comparison
        cmp_path = ROOT / "data/processed/spike_compare_template.csv"
    with open(cmp_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["plan_key", "plan_name", "our_drug_oop", "plan_finder_drug_cost", "error_pct"])
        for i in idx:
            r, pname, _ = results[i]
            w.writerow([r.plan_key, pname, r.drug_oop, "", ""])
    print(f"\nFill in Plan Finder numbers here: {cmp_path}")


if __name__ == "__main__":
    main()
