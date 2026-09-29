"""Tools the agent can call. Every number comes from the deterministic engine, never from the LLM."""
from __future__ import annotations

import json

from engine import data, rxnorm
from engine.estimate import estimate

SCHEMAS = [
    {"type": "function", "function": {
        "name": "find_drug",
        "description": "REQUIRED for every medication before compare_plans. Look up a medication the user mentioned "
                       "(brand or generic, with or without strength or device, e.g. 'Lantus SoloStar pen'). "
                       "Returns exact RxNorm names with strength and form. Use the exact rxnorm_name in compare_plans. "
                       "If several strengths match and the user did not say which, ask them.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What the user said, e.g. 'Eliquis 5 mg' or 'metformin 500'"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "find_county",
        "description": "List valid county names for a state (needed before compare_plans).",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string", "description": "Full state name, e.g. Florida"},
            "contains": {"type": "string", "description": "Optional text to filter county names"}},
            "required": ["state"]}}},
    {"type": "function", "function": {
        "name": "compare_plans",
        "description": "Rank every Medicare plan available in a county for this person: premium + drug costs "
                       "(+ expected medical costs), star ratings, uncovered drugs, generic-switch alerts. "
                       "Call only after drugs and county are confirmed.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string"}, "county": {"type": "string"},
            "drugs": {"type": "array", "items": {"type": "object", "properties": {
                "rxnorm_name": {"type": "string"},
                "qty_per_30d": {"type": "number", "description":
                    "Units per 30 days. Tablets/capsules: count (60 = twice daily). Insulin: mL, where "
                    "100 units = 1 mL (20 units/day -> 6 mL); pens are 3 mL each, round up to whole pens (6 mL). "
                    "Eye drops: mL (one 2.5 mL bottle ~ 1 month)."}},
                "required": ["rxnorm_name", "qty_per_30d"]}},
            "health_usage": {"type": "string", "enum": ["low", "medium", "high"]},
            "medicaid": {"type": "boolean", "description": "Has Medicaid too (dual eligible)"},
            "chronic_conditions": {"type": "array", "items": {"type": "string"},
                                   "description": "Diagnoses the user stated, e.g. ['heart failure','diabetes']. "
                                                  "Used only to check eligibility for condition-specific plans (C-SNPs)."},
            "top_n": {"type": "integer", "description": "How many plans to return (default 5)"}},
            "required": ["state", "county", "drugs"]}}},
]


def find_drug(query: str) -> dict:
    return {"matches": rxnorm.search(query)}


def find_county(state: str, contains: str | None = None) -> dict:
    con = data.connect()
    names = [c for _, c in data.counties(con, state)]
    if contains:
        names = [c for c in names if contains.lower() in c.lower()]
    return {"state": state, "counties": names[:50]}


def compare_plans(state: str, county: str, drugs: list[dict], health_usage: str | None = None,
                  medicaid: bool = False, chronic_conditions: list[str] | None = None, top_n: int = 5) -> dict:
    bad = [d["rxnorm_name"] for d in drugs if not rxnorm.exact_rxcui(d["rxnorm_name"])]
    if bad:
        return {"error": "These are not exact RxNorm names: " + "; ".join(bad) +
                         ". Call find_drug for each one and use a rxnorm_name it returns (ask the user which "
                         "form/strength if several match). Do not guess names."}
    person = {"state": state, "county": county, "medicaid": medicaid,
              "chronic_conditions": chronic_conditions or [], "health_usage": health_usage,
              "drugs": [{"name": d["rxnorm_name"], "qty_per_30d": d["qty_per_30d"]} for d in drugs]}
    out = estimate(person)
    keep = ("plan_key", "plan_name", "type", "organization", "star_overall", "moop", "annual_premium",
            "drug_oop", "drug_oop_is_lower_bound", "total", "bad_year_total", "not_covered", "with_generics",
            "generic_alerts", "snp_type", "needs_snp_verification", "medical_note")
    def slim(r: dict) -> dict:
        p = {k: r.get(k) for k in keep}
        p["generic_alerts"] = [a["message"] for a in r.get("generic_alerts", [])]
        p["drug_flags"] = {d["drug"]: d.get("flags") for d in r["drugs"] if d.get("flags")}
        p["snp_eligibility"] = r.get("snp_eligibility")
        p["plain_summary"] = r.get("plain_summary")
        return p

    regular = [slim(r) for r in out["results"] if not r.get("snp_type")][:top_n]
    snp = [slim(r) for r in out["results"] if r.get("snp_type")][:2]
    everything_covered = any(not r["not_covered"] for r in out["results"] if not r.get("snp_type"))

    def wg_key(r):
        wg = r.get("with_generics") or {"not_covered": r["not_covered"], "rank_score": r["rank_score"]}
        return (len(wg["not_covered"]), wg["rank_score"], -(r.get("star_overall") or 0))
    best_generics = [slim(r) for r in sorted((r for r in out["results"] if not r.get("snp_type") and r.get("with_generics")),
                                             key=wg_key)][:3]
    return {"plan_year": out["year"], "market": out["market"], "data_as_of": out["data_as_of"],
            "part_b_monthly_premium": out.get("part_b_monthly_premium"),
            "plans_considered": out["plans_ranked"], "excluded_snp_plans": out["plans_excluded_by_snp_eligibility"],
            "top_plans": regular, "special_needs_plan_options": snp,
            "a_regular_plan_covers_every_drug_as_prescribed": everything_covered,
            "best_if_doctor_approves_generics": best_generics,
            "field_guide": {
                "plain_summary": "accurate plain-language summary of each plan - base your explanation on it",
                "part_b_monthly_premium": "standard Part B premium she pays on top of any plan premium",
                "total": "typical year = 12 months of premium + drug out-of-pocket",
                "bad_year_total": "typical year + medical out-of-pocket max (moop): the most she'd pay if she had "
                                  "a very bad health year (hospital stays etc.)",
                "with_generics": "the same plan if her doctor approves the listed generic switch(es)",
                "best_if_doctor_approves_generics": "best plans assuming the doctor approves generic switches - "
                                                    "present as an option to discuss with the doctor",
                "drug_oop_is_lower_bound": "true = a drug is not covered; real cost is at least this, often 2-3x",
                "generic_alerts": "cheaper generic on the same plan - suggest asking the doctor, never switch alone",
                "drug_flags": "PA = prior authorization, ST = step therapy, QL = quantity limit",
                "special_needs_plan_options": "C-SNP/D-SNP plans she appears eligible for; eligibility must be "
                                              "confirmed by the plan",
            },
            "assumptions": out["assumptions"]}


IMPL = {"find_drug": find_drug, "find_county": find_county, "compare_plans": compare_plans}


def call(name: str, args_json: str) -> str:
    try:
        args = json.loads(args_json or "{}")
        return json.dumps(IMPL[name](**args), default=str)
    except Exception as e:  # tool errors go back to the model so it can recover
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
