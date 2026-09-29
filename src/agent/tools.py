"""Tools the agent can call. Every number comes from the deterministic engine, never from the LLM."""
from __future__ import annotations

import json

from engine import data, rxnorm
from engine.estimate import estimate

SCHEMAS = [
    {"type": "function", "function": {
        "name": "find_drug",
        "description": "Look up a medication the user mentioned (brand or generic, with or without strength). "
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
                "qty_per_30d": {"type": "number", "description": "Units per month, e.g. 60 for twice-daily tablets"}},
                "required": ["rxnorm_name", "qty_per_30d"]}},
            "health_usage": {"type": "string", "enum": ["low", "medium", "high"]},
            "medicaid": {"type": "boolean", "description": "Has Medicaid too (dual eligible)"},
            "chronic_conditions": {"type": "array", "items": {"type": "string"}},
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
    person = {"state": state, "county": county, "medicaid": medicaid,
              "chronic_conditions": chronic_conditions or [], "health_usage": health_usage,
              "drugs": [{"name": d["rxnorm_name"], "qty_per_30d": d["qty_per_30d"]} for d in drugs]}
    out = estimate(person)
    keep = ("plan_key", "plan_name", "type", "organization", "star_overall", "moop", "annual_premium",
            "drug_oop", "drug_oop_is_lower_bound", "total", "expected_total", "bad_year_total", "not_covered",
            "generic_alerts", "snp_type", "needs_snp_verification", "medical_note")
    plans = []
    for r in out["results"][:top_n]:
        p = {k: r.get(k) for k in keep}
        p["generic_alerts"] = [a["message"] for a in r.get("generic_alerts", [])]
        p["drug_flags"] = {d["drug"]: d.get("flags") for d in r["drugs"] if d.get("flags")}
        plans.append(p)
    return {"plan_year": out["year"], "market": out["market"], "data_as_of": out["data_as_of"],
            "plans_considered": out["plans_ranked"], "excluded_snp_plans": out["plans_excluded_by_snp_eligibility"],
            "top_plans": plans, "assumptions": out["assumptions"]}


IMPL = {"find_drug": find_drug, "find_county": find_county, "compare_plans": compare_plans}


def call(name: str, args_json: str) -> str:
    try:
        args = json.loads(args_json or "{}")
        return json.dumps(IMPL[name](**args), default=str)
    except Exception as e:  # tool errors go back to the model so it can recover
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
