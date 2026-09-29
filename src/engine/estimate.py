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



def estimate_plan(con, plan, drugs: list[dict], pharmacy: str = "preferred_retail", year: int = 2026) -> dict:
    """Annual cost for one plan. `drugs` items need name, qty_per_30d, rxcui, ndcs."""
    fills, detail = [], []
    for d in drugs:
        fe = data.formulary_entry(con, plan.formulary_id, [d["rxcui"], *d.get("equivalents", [])])
        if not fe:
            mkt = data.market_unit_cost(con, d.get("oracle_ndc"), d["ndcs"])
            fills.append(DrugFill(d["name"], None, d["qty_per_30d"], False, uncovered_unit_cost=mkt))
            detail.append({"drug": d["name"], "covered": False,
                           "monthly_full_price": round((mkt or 0) * d["qty_per_30d"], 2),
                           "full_price_is_lower_bound": True,
                           "note": ("not on formulary: you pay the pharmacy's cash price (at least this much, often "
                                    "2-3x more), and it does not count toward the cap"
                                    if mkt else "not on formulary and no public price found: cost unknown")})
            continue
        unit, price_src = data.unit_cost(con, plan, fe.representative_ndc, d["ndcs"])
        is_insulin = "insulin" in d["name"].lower()
        cs = (data.insulin_cost_share if is_insulin else data.cost_share)(con, plan, fe.tier, pharmacy)
        fills.append(DrugFill(d["name"], unit, d["qty_per_30d"], unit is not None, fe.tier,
                              cs.cost_type, cs.amount, cs.deductible_applies, fe.flags))
        detail.append({"drug": d["name"], "covered": True, "tier": fe.tier, "flags": fe.flags,
                       "monthly_drug_cost": round((unit or 0) * d["qty_per_30d"], 2),
                       "cost_type": cs.cost_type, "cost_amount": cs.amount,
                       "pharmacy_used": cs.pharmacy_used, "price_source": price_src})
    r = annual_cost(plan.key, plan.monthly_premium, plan.drug_deductible, fills, year)
    return {
        "plan_key": plan.key, "plan_name": plan.name, "type": "PDP" if plan.is_pdp else "MA-PD",
        "snp_type": plan.snp_type, "needs_snp_verification": plan.snp_type == "C-SNP",
        "annual_premium": r.annual_premium, "drug_deductible": plan.drug_deductible,
        "drug_oop": r.drug_oop, "covered_oop": r.covered_oop, "uncovered_cost": r.uncovered_cost,
        "drug_oop_is_lower_bound": r.uncovered_cost > 0,
        "total": r.total, "monthly_oop": r.monthly_oop,
        "hit_cap_month": r.hit_cap_month, "not_covered": r.not_covered, "drugs": detail,
    }

GENERIC_ALERT_MIN_SAVINGS = 100.0  # $/year


def generic_alerts(con, plan, drugs: list[dict], pharmacy: str, year: int, base_oop: float) -> list[dict]:
    """For each brand drug with a generic, re-price the plan with the generic swapped in."""
    alerts = []
    for i, d in enumerate(drugs):
        g = d.get("generic")
        if not g:
            continue
        swapped = drugs[:i] + [{"name": g["name"], "qty_per_30d": d["qty_per_30d"], "rxcui": g["rxcui"],
                                "ndcs": g["ndcs"], "equivalents": g.get("equivalents", [])}] + drugs[i + 1:]
        alt = estimate_plan(con, plan, swapped, pharmacy, year)
        saving = round(base_oop - alt["drug_oop"], 2)
        if saving >= GENERIC_ALERT_MIN_SAVINGS:
            gd = next(x for x in alt["drugs"] if x["drug"] == g["name"])
            alerts.append({"brand": d["name"], "generic": g["name"], "annual_savings": saving,
                           "generic_covered": gd["covered"], "generic_tier": gd.get("tier"),
                           "savings_is_lower_bound": base_oop > 0 and any(
                               not x["covered"] for x in estimate_plan(con, plan, [d], pharmacy, year)["drugs"]),
                           "message": f"Ask your doctor whether {g['name']} can replace {d['name']}: "
                                      f"at least ${saving:,.0f}/year less on this plan."})
    return alerts


def estimate(person: dict, year: int | None = None, con=None) -> dict:
    con = con or data.connect()
    data.load_market(con, person.get("state", "Florida"), person.get("county", "Miami-Dade"))
    m = data.manifest()
    year = year or int(m["benefit_year"])
    pharmacy = person.get("pharmacy", "preferred_retail")
    drugs = []
    for d in person["drugs"]:
        info = rxnorm.lookup(d["name"])  # adds equivalents + generic alternative (cached)
        drugs.append({**info, **d, "equivalents": info.get("equivalents", []), "generic": info.get("generic")})

    allowed = eligible_snp_types(person)
    results, skipped = [], {}
    for plan in data.plans(con):
        if plan.snp_type not in allowed:
            skipped[plan.snp_type] = skipped.get(plan.snp_type, 0) + 1
            continue
        r = estimate_plan(con, plan, drugs, pharmacy, year)
        r["generic_alerts"] = generic_alerts(con, plan, drugs, pharmacy, year, r["drug_oop"])
        results.append(r)
    results.sort(key=lambda x: (len(x["not_covered"]), x["total"]))
    assumptions_extra = []
    if str(m.get("price_year")) != str(m.get("benefit_year")):
        assumptions_extra.append(f"Drug prices are {m['price_year']} negotiated prices applied to "
                                 f"{m['benefit_year']} plan benefits (CMS has not yet published {m['benefit_year']} prices)")
    return {
        "year": year, "market": {"state": person.get("state", "Florida"), "county": person.get("county", "Miami-Dade")},
        "data_as_of": {"coverage": m["sources"]["monthly"]["release"], "prices": m["sources"]["quarterly"]["release"],
                       "release_id": m["release_id"]},
        "pharmacy": pharmacy, "plans_ranked": len(results),
        "plans_excluded_by_snp_eligibility": {str(k): v for k, v in skipped.items()},
        "assumptions": [
            "One 30-day fill per drug per month at the chosen pharmacy type",
            "Plan's negotiated price for CMS's representative NDC (median across NDCs if missing)",
            "Premium shown is the plan premium; Part B premium not included",
            "Drugs not on a plan's formulary are shown at the plans' negotiated price as a LOWER BOUND: "
            "the pharmacy cash price is often 2-3x higher, and it does not count toward the out-of-pocket cap",
            "Pharmacy dispensing fees not included; brand drugs may cost $0-30 more per month "
            "on plans with a deductible or coinsurance",
        ] + assumptions_extra,
        "results": results,
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    person = json.loads(Path(args[0]).read_text())
    year = int(sys.argv[sys.argv.index("--year") + 1]) if "--year" in sys.argv else None
    out = estimate(person, year)
    if "--json" in sys.argv:
        print(json.dumps(out, indent=1))
        return
    print(f"{out['market']['county']}, {out['market']['state']} | plan year {out['year']} | data as of {out['data_as_of']}")
    print(f"{out['plans_ranked']} plans ranked; excluded by SNP eligibility: {out['plans_excluded_by_snp_eligibility']}")
    for r in out["results"][:10]:
        nc = f"  NOT COVERED: {', '.join(r['not_covered'])}" if r["not_covered"] else ""
        lb = "+" if r.get("drug_oop_is_lower_bound") else " "
        snp = f" [{r['snp_type']}]" if r["snp_type"] else ""
        print(f"  {r['plan_key']:15} ${r['total']:>8,.0f}{lb} = drugs ${r['drug_oop']:,.0f}{lb} + premium "
              f"${r['annual_premium']:,.0f}  {r['type']:5} {r['plan_name'][:42]}{snp}{nc}")
        for a in r.get("generic_alerts", []):
            print(f"      -> GENERIC: {a['message']}")


if __name__ == "__main__":
    main()
