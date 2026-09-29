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


# Person's condition words -> CMS C-SNP condition codes (Landscape "csnp_condition")
CSNP_KEYWORDS = {
    "ChronicHeartFailure": ["heart failure", "chf", "hfref", "hfpef"],
    "CardiovascularDisorders": ["heart", "cardio", "coronary", "afib", "atrial fibrillation", "arrhythmia",
                                "vascular", "stroke"],
    "DiabetesMellitus": ["diabet", "type 2", "type 1"],
    "ChronicLungDisorders": ["copd", "lung", "asthma", "emphysema", "pulmonary"],
    "ChronicKidneyDisease": ["kidney", "renal", "ckd", "dialysis", "esrd"],
    "Dementia": ["dementia", "alzheimer"],
    "ChronicMentalHealth": ["depress", "bipolar", "schizo", "mental"],
}


def person_csnp_codes(person: dict) -> set[str]:
    text = " ".join(person.get("chronic_conditions") or []).lower()
    return {code for code, words in CSNP_KEYWORDS.items() if any(w in text for w in words)}


def snp_eligible(plan, person: dict) -> tuple[bool, str | None]:
    """Can this person join this plan? Returns (eligible, why)."""
    if plan.snp_type is None:
        return True, None
    if plan.snp_type == "D-SNP":
        return (True, "Has Medicaid") if person.get("medicaid") else (False, "D-SNP needs Medicaid")
    if plan.snp_type == "I-SNP":
        return (True, "Lives in a facility") if person.get("institutional") else (False, "I-SNP needs facility care")
    codes = set((plan.csnp_condition or "").split(",")) - {"", "Not Applicable"}
    match = codes & person_csnp_codes(person)
    if match:
        return True, "Condition match: " + ", ".join(sorted(match)) + " (plan must confirm diagnosis)"
    return False, f"C-SNP for {', '.join(sorted(codes)) or 'other conditions'}"



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
                       "pharmacy_used": cs.pharmacy_used, "price_source": price_src,
                       "representative_ndc": fe.representative_ndc})
    r = annual_cost(plan.key, plan.monthly_premium, plan.drug_deductible, fills, year)
    return {
        "plan_key": plan.key, "plan_name": plan.name, "type": "PDP" if plan.is_pdp else "MA-PD",
        "snp_type": plan.snp_type, "needs_snp_verification": plan.snp_type == "C-SNP",
        "organization": plan.organization, "plan_type": plan.plan_type,
        "star_overall": plan.star_overall, "star_part_d": plan.star_part_d, "moop": plan.moop,
        "csnp_condition": plan.csnp_condition,
        "annual_premium": r.annual_premium, "drug_deductible": plan.drug_deductible,
        "drug_oop": r.drug_oop, "covered_oop": r.covered_oop, "uncovered_cost": r.uncovered_cost,
        "drug_oop_is_lower_bound": r.uncovered_cost > 0,
        "total": r.total, "monthly_oop": r.monthly_oop,
        "hit_cap_month": r.hit_cap_month, "not_covered": r.not_covered, "drugs": detail,
    }

GENERIC_ALERT_MIN_SAVINGS = 100.0  # $/year
# For RANKING only: an uncovered drug's true cash price is usually 2-3x our lower bound; rank as if 3x.
UNCOVERED_RANK_MULTIPLIER = 3.0
# Standard Part B premium, paid by everyone on top of plan premiums. Source: Medicare Plan Finder (2026).
PART_B_PREMIUM = {2026: 202.90}


def plain_summary(r: dict) -> str:
    """Deterministic one-paragraph summary so the LLM never has to assemble facts itself."""
    lb = " (at least - a drug is not covered)" if r.get("drug_oop_is_lower_bound") else ""
    parts = [f"{r['plan_name']}: about ${r['total']:,.0f} in a typical year{lb} "
             f"(premium ${r['annual_premium']:,.0f} + drugs ${r['drug_oop']:,.0f})."]
    if r.get("bad_year_total") is not None:
        parts.append(f"In a very bad health year, at most about ${r['bad_year_total']:,.0f} "
                     f"(medical out-of-pocket max ${r['moop']:,.0f}).")
    elif r.get("medical_note"):
        parts.append(r["medical_note"] + ".")
    if r.get("star_overall"):
        parts.append(f"Medicare star rating {r['star_overall']:.1f} of 5.")
    for d in r.get("not_covered", []):
        parts.append(f"NOT covered: {d} - she would pay the pharmacy cash price, which does not count toward any cap.")
    for a in r.get("generic_alerts", []):
        parts.append(a["message"])
    limits = [f"{d['drug']} ({', '.join(d['flags'])})" for d in r.get("drugs", []) if d.get("flags")]
    if limits:
        parts.append("Coverage rules to check: " + "; ".join(limits) +
                     " (PA = prior authorization, ST = step therapy, QL = quantity limit).")
    wg = r.get("with_generics")
    if wg:
        lbg = " (at least)" if wg["drug_oop_is_lower_bound"] else ""
        cov = "with every drug covered" if not wg["not_covered"] else "still not covering " + ", ".join(wg["not_covered"])
        parts.append(f"If her doctor approves the generic(s), this plan would cost about ${wg['total']:,.0f}{lbg} "
                     f"in a typical year, {cov}.")
    if r.get("snp_eligibility"):
        parts.append("Special needs plan - " + r["snp_eligibility"] + ".")
    return " ".join(parts)
# Heuristic chance of a "bad health year" that reaches the medical out-of-pocket max (disclosed to user).
BAD_YEAR_RISK = {"low": 0.05, "medium": 0.15, "high": 0.50}


def add_medical(r: dict, person: dict) -> None:
    usage = person.get("health_usage") or ("high" if person.get("chronic_conditions") else "medium")
    risk = BAD_YEAR_RISK.get(usage, 0.15)
    r["health_usage"] = usage
    if r["type"] == "MA-PD" and r.get("moop") is not None:
        r["bad_year_total"] = round(r["total"] + r["moop"], 2)
        r["expected_total"] = round(r["total"] + risk * r["moop"], 2)
        r["medical_note"] = None
    else:  # PDP: medical costs depend on Original Medicare + optional Medigap (no cap without Medigap)
        r["bad_year_total"] = None
        r["expected_total"] = r["total"]
        r["medical_note"] = "Stand-alone drug plan: medical costs not included (Original Medicare has no out-of-pocket cap unless you buy Medigap)"


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
        gd = next(x for x in alt["drugs"] if x["drug"] == g["name"])
        # Only alert if a real generic product is on this plan: covered, and priced from a GENERIC NDC.
        # (Some formularies list a brand under the generic RXCUI with the brand's NDC, e.g. apixaban/Eliquis
        # before any generic is marketed - that must not trigger "switch to the generic".)
        generic_ndcs = set(g["ndcs"])
        real_generic = gd["covered"] and (
            (gd.get("price_source") == "representative_ndc" and gd.get("representative_ndc") in generic_ndcs)
            or (gd.get("price_source") == "median_ndc" and gd.get("representative_ndc") not in set(d.get("ndcs", []))))
        if saving >= GENERIC_ALERT_MIN_SAVINGS and real_generic:
            alerts.append({"_generic_drug": swapped[i], "brand": d["name"], "generic": g["name"], "annual_savings": saving,
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

    results, skipped = [], {}
    for plan in data.plans(con):
        ok, why = snp_eligible(plan, person)
        if not ok:
            skipped[plan.snp_type] = skipped.get(plan.snp_type, 0) + 1
            continue
        r = estimate_plan(con, plan, drugs, pharmacy, year)
        r["generic_alerts"] = generic_alerts(con, plan, drugs, pharmacy, year, r["drug_oop"])
        add_medical(r, person)
        r["snp_eligibility"] = why
        r["with_generics"] = None
        if r["generic_alerts"]:
            swap = {a["brand"]: a["_generic_drug"] for a in r["generic_alerts"]}
            alt = estimate_plan(con, plan, [swap.get(d["name"], d) for d in drugs], pharmacy, year)
            add_medical(alt, person)
            r["with_generics"] = {"switched": [f"{b} -> {g['name']}" for b, g in swap.items()],
                                  "total": alt["total"], "drug_oop": alt["drug_oop"],
                                  "bad_year_total": alt.get("bad_year_total"), "not_covered": alt["not_covered"],
                                  "drug_oop_is_lower_bound": alt["drug_oop_is_lower_bound"],
                                  "rank_score": alt["expected_total"] + (UNCOVERED_RANK_MULTIPLIER - 1) * alt["uncovered_cost"]}
        r["rank_score"] = r["expected_total"] + (UNCOVERED_RANK_MULTIPLIER - 1) * r["uncovered_cost"]
        r["plain_summary"] = plain_summary(r)
        r["plain_summary"] = plain_summary(r)
        results.append(r)
    results.sort(key=lambda x: (len(x["not_covered"]), x["rank_score"], -(x.get("star_overall") or 0)))
    assumptions_extra = []
    if str(m.get("price_year")) != str(m.get("benefit_year")):
        assumptions_extra.append(f"Drug prices are {m['price_year']} negotiated prices applied to "
                                 f"{m['benefit_year']} plan benefits (CMS has not yet published {m['benefit_year']} prices)")
    return {
        "year": year, "market": {"state": person.get("state", "Florida"), "county": person.get("county", "Miami-Dade")},
        "data_as_of": {"coverage": m["sources"]["monthly"]["release"], "prices": m["sources"]["quarterly"]["release"],
                       "release_id": m["release_id"]},
        "part_b_monthly_premium": PART_B_PREMIUM.get(year),
        "pharmacy": pharmacy, "plans_ranked": len(results),
        "plans_excluded_by_snp_eligibility": {str(k): v for k, v in skipped.items()},
        "assumptions": [
            "One 30-day fill per drug per month at the chosen pharmacy type",
            "Plan's negotiated price for CMS's representative NDC (median across NDCs if missing)",
            "Premium is the plan's monthly Part C + D premium; the standard Part B premium is not included",
            "Ranking (not shown as a cost): premium + drugs + an assumed chance of a bad health year (5% / 15% / 50% "
            "for low / medium / high use) x the medical out-of-pocket max; uncovered drugs count 3x their lower bound",
            "Ties are broken by CMS overall star rating",
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
        star = f"{r['star_overall']:.1f}*" if r.get("star_overall") else "  - "
        moop = f"MOOP ${r['moop']:,.0f}" if r.get("moop") is not None else "no MOOP  "
        print(f"  {r['plan_key']:15} expected ${r['expected_total']:>7,.0f}{lb} | typical ${r['total']:>7,.0f}{lb} "
              f"(drugs ${r['drug_oop']:,.0f} + prem ${r['annual_premium']:,.0f}) | {moop:12} {star} "
              f"{r['type']:5} {r['plan_name'][:38]}{snp}{nc}")
        for a in r.get("generic_alerts", []):
            print(f"      -> GENERIC: {a['message']}")


if __name__ == "__main__":
    main()
