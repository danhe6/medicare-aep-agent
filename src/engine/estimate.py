"""Rank every Miami-Dade plan for one person: premium + estimated Part D out-of-pocket.

    python -m engine.estimate evals/personas/spike.json         (run with PYTHONPATH=src)

Returns / prints JSON-able results, which is what the agent tool will call.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from engine import data, rxnorm
from engine.part_d_cost import DrugFill, annual_cost


def eligible_snp_types(person: dict) -> set:
    """Which SNP types this person may join. Non-SNP plans (None) are always allowed."""
    ok = {None}
    if person.get("medicaid"):
        ok.add("D-SNP")
    if person.get("chronic_conditions"):
        ok.add("C-SNP")  # condition match per plan still needs confirmation (flagged in output)
    if person.get("institutional"):
        ok.add("I-SNP")
    return ok


def estimate(person: dict, year: int = 2026, con=None) -> dict:
    con = con or data.connect()
    pharmacy = person.get("pharmacy", "preferred_retail")
    drugs = []
    for d in person["drugs"]:
        info = rxnorm.lookup(d["name"])
        drugs.append({**d, **info})

    allowed = eligible_snp_types(person)
    results, skipped = [], {}
    for plan in data.plans(con):
        if plan.snp_type not in allowed:
            skipped[plan.snp_type] = skipped.get(plan.snp_type, 0) + 1
            continue
        fills, detail = [], []
        for d in drugs:
            fe = data.formulary_entry(con, plan.formulary_id, d["rxcui"])
            if not fe:
                fills.append(DrugFill(d["name"], None, d["qty_per_30d"], False))
                detail.append({"drug": d["name"], "covered": False})
                continue
            unit, price_src = data.unit_cost(con, plan, fe.representative_ndc, d["ndcs"])
            cs = data.cost_share(con, plan, fe.tier, pharmacy)
            fills.append(DrugFill(d["name"], unit, d["qty_per_30d"], unit is not None, fe.tier,
                                  cs.cost_type, cs.amount, cs.deductible_applies, fe.flags))
            detail.append({"drug": d["name"], "covered": True, "tier": fe.tier, "flags": fe.flags,
                           "monthly_drug_cost": round((unit or 0) * d["qty_per_30d"], 2),
                           "cost_type": cs.cost_type, "cost_amount": cs.amount,
                           "pharmacy_used": cs.pharmacy_used, "price_source": price_src})
        r = annual_cost(plan.key, plan.monthly_premium, plan.drug_deductible, fills, year)
        results.append({
            "plan_key": plan.key, "plan_name": plan.name, "type": "PDP" if plan.is_pdp else "MA-PD",
            "snp_type": plan.snp_type, "needs_snp_verification": plan.snp_type == "C-SNP",
            "annual_premium": r.annual_premium, "drug_deductible": plan.drug_deductible,
            "drug_oop": r.drug_oop, "total": r.total, "monthly_oop": r.monthly_oop,
            "hit_cap_month": r.hit_cap_month, "not_covered": r.not_covered, "drugs": detail,
        })
    results.sort(key=lambda x: (len(x["not_covered"]), x["total"]))
    return {
        "year": year, "pharmacy": pharmacy, "plans_ranked": len(results),
        "plans_excluded_by_snp_eligibility": {str(k): v for k, v in skipped.items()},
        "assumptions": [
            "One 30-day fill per drug per month at the chosen pharmacy type",
            "Plan's negotiated price for CMS's representative NDC (median across NDCs if missing)",
            "Premium shown is the plan premium; Part B premium not included",
            "Drugs not on the formulary are listed, not priced",
            "Pharmacy dispensing fees not included; brand drugs may cost $0-30 more per month "
            "on plans with a deductible or coinsurance",
        ],
        "results": results,
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    person = json.loads(Path(args[0]).read_text())
    year = int(sys.argv[sys.argv.index("--year") + 1]) if "--year" in sys.argv else 2026
    out = estimate(person, year)
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
        return
    print(f"{out['plans_ranked']} plans ranked; excluded by SNP eligibility: {out['plans_excluded_by_snp_eligibility']}")
    for r in out["results"][:10]:
        nc = f"  NOT COVERED: {', '.join(r['not_covered'])}" if r["not_covered"] else ""
        snp = f" [{r['snp_type']}]" if r["snp_type"] else ""
        print(f"  {r['plan_key']:15} ${r['total']:>8,.0f} = drugs ${r['drug_oop']:,.0f} + premium "
              f"${r['annual_premium']:,.0f}  {r['type']:5} {r['plan_name'][:42]}{snp}{nc}")


if __name__ == "__main__":
    main()
