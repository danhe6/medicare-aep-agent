"""Tools the agent can call. Every number comes from the deterministic engine, never from the LLM."""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

from engine import data, rxnorm
from engine.estimate import estimate
from defend.notice import analyze as analyze_notice
from letters.read import analyze as analyze_letter
from meds.label import analyze as analyze_label
from engine.usage import infer_health_usage
from network.doctor import check as check_doctor
from engine import extra_help
from engine.estimate import friendly_name

ROOT = Path(__file__).resolve().parents[2]

SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_medicare_letter",
        "description": "Use for ANY photo or PDF of a Medicare-related letter or notice the user uploads: drug or medical "
                       "coverage denial, prior authorization denial, Notice of Medicare Non-Coverage (care ending), "
                       "Medicare Summary Notice, IRMAA (Social Security premium) letter, Annual Notice of Change, EOB. "
                       "It identifies the letter, extracts the key facts, computes the deadline with Medicare's rules, "
                       "lists the steps, and drafts an appeal letter and a request to the doctor where an appeal applies.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "Path to the uploaded photo or PDF"}},
            "required": ["file_path"]}}},
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
            "hospital_stay_last_year": {"type": "boolean", "description": "Only if the user said so"},
            "pharmacy": {"type": "string", "enum": ["preferred_retail", "standard_retail", "preferred_mail"],
                         "description": "Where she fills prescriptions. Default preferred_retail. Use preferred_mail "
                                        "for 'what if she uses mail order'."},
            "top_n": {"type": "integer", "description": "How many plans to return (default 5)"}},
            "required": ["state", "county", "drugs"]}}},
    {"type": "function", "function": {
        "name": "check_doctor_network",
        "description": "Look for evidence that a doctor is in the network of the insurers behind the plans you "
                       "discussed (NPI registry + web search of provider directories). Evidence only - always tell "
                       "the user to call the plan or the doctor's office to confirm before enrolling.",
        "parameters": {"type": "object", "properties": {
            "doctor_name": {"type": "string", "description": "As the user said it, e.g. 'Dr. Maria Lopez'"},
            "state": {"type": "string"}, "city": {"type": "string", "description": "City or county, if known"},
            "specialty": {"type": "string", "description": "e.g. 'Family Medicine', 'Cardiology' - use after the user picks one of several matches"},
            "organizations": {"type": "array", "items": {"type": "string"},
                              "description": "The 'organization' of each plan to check, from compare_plans results"}},
            "required": ["doctor_name", "state", "organizations"]}}},
    {"type": "function", "function": {
        "name": "check_current_plan",
        "description": "Use when the user names the plan she is in NOW (or asks 'should she stay?', or has her "
                       "Annual Notice of Change). Shows what that plan costs her this year, its published changes "
                       "for next year (premium, out-of-pocket max, whether it continues), its track record, and "
                       "the best alternative with the savings. Same inputs as compare_plans plus current_plan.",
        "parameters": {"type": "object", "properties": {
            "current_plan": {"type": "string", "description": "Plan name as the user says it, or its ID like H1019-057"},
            "state": {"type": "string"}, "county": {"type": "string"},
            "drugs": {"type": "array", "items": {"type": "object", "properties": {
                "rxnorm_name": {"type": "string"}, "qty_per_30d": {"type": "number"}},
                "required": ["rxnorm_name", "qty_per_30d"]}},
            "medicaid": {"type": "boolean"}, "chronic_conditions": {"type": "array", "items": {"type": "string"}},
            "hospital_stay_last_year": {"type": "boolean"}},
            "required": ["current_plan", "state", "county", "drugs"]}}},
    {"type": "function", "function": {
        "name": "screen_extra_help",
        "description": "Quick check whether she may qualify for Extra Help (Medicare's Part D low-income subsidy), "
                       "and roughly what her medicines would cost with it. Ask for yearly income and savings only "
                       "if the user wants this check; never save them.",
        "parameters": {"type": "object", "properties": {
            "married": {"type": "boolean", "description": "Married and living together"},
            "state": {"type": "string"},
            "yearly_income": {"type": "number", "description": "Before taxes, all sources (Social Security, pensions...)"},
            "resources": {"type": "number", "description": "Savings, checking, stocks, bonds. NOT the home or one car"},
            "has_medicaid_ssi_or_msp": {"type": "boolean"},
            "drugs": {"type": "array", "items": {"type": "string"}, "description": "rxnorm_name of her medicines, if known"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "read_medicine_label",
        "description": "Use when the user sends a photo of a prescription bottle, pharmacy label or medicine box. "
                       "Reads the name, strength, directions and quantity, and works out how many per 30 days.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "Path to the uploaded photo"}},
            "required": ["file_path"]}}},
    {"type": "function", "function": {
        "name": "update_profile",
        "description": "Save facts the user confirmed to the health profile stored ON THEIR DEVICE (not on our servers), "
                       "so they never have to repeat them: where they live, Medicaid, conditions, hospital stay, and "
                       "medicines added or stopped. Call it whenever the user tells you something new or confirms a "
                       "label. Never save Medicare numbers, Social Security numbers or other ID numbers.",
        "parameters": {"type": "object", "properties": {
            "person": {"type": "string", "description": "Who this is about, as the user says it: 'me', 'Mom', 'Dad'"},
            "state": {"type": "string"}, "county": {"type": "string"}, "medicaid": {"type": "boolean"},
            "conditions": {"type": "array", "items": {"type": "string"}},
            "hospital_stay_last_year": {"type": "boolean"},
            "current_plan": {"type": "string", "description": "plan_key of the plan she is in now, e.g. H1019-057-000"},
            "current_plan_name": {"type": "string", "description": "That plan's name as shown in the results"},
            "add_medicines": {"type": "array", "items": {"type": "object", "properties": {
                "rxnorm_name": {"type": "string"}, "qty_per_30d": {"type": "number"},
                "directions": {"type": "string"}}, "required": ["rxnorm_name", "qty_per_30d"]}},
            "stop_medicines": {"type": "array", "items": {"type": "string"},
                               "description": "rxnorm_name of medicines the user no longer takes"}},
            "required": ["person"]}}},
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
                  medicaid: bool = False, chronic_conditions: list[str] | None = None, top_n: int = 5,
                  hospital_stay_last_year: bool | None = None, pharmacy: str = "preferred_retail", lang: str = "en") -> dict:
    bad = [d["rxnorm_name"] for d in drugs if not rxnorm.exact_rxcui(d["rxnorm_name"])]
    if bad:
        return {"error": "These are not exact RxNorm names: " + "; ".join(bad) +
                         ". Call find_drug for each one and use a rxnorm_name it returns (ask the user which "
                         "form/strength if several match). Do not guess names."}
    usage = infer_health_usage([d["rxnorm_name"] for d in drugs], chronic_conditions, hospital_stay_last_year)
    if health_usage in ("low", "medium", "high"):
        usage = {"level": health_usage, "reasons": ["the user said so"], "explain": f"You told me {health_usage} use."}
    health_usage = usage["level"]
    person = {"state": state, "county": county, "medicaid": medicaid, "pharmacy": pharmacy,
              "chronic_conditions": chronic_conditions or [], "health_usage": health_usage,
              "drugs": [{"name": d["rxnorm_name"], "qty_per_30d": d["qty_per_30d"]} for d in drugs]}
    out = estimate(person, lang=lang)
    keep = ("plan_key", "plan_name", "type", "organization", "star_overall", "moop", "annual_premium",
            "drug_oop", "drug_oop_is_lower_bound", "total", "bad_year_total", "not_covered", "with_generics",
            "generic_alerts", "snp_type", "needs_snp_verification", "medical_note", "track_record")
    def slim(r: dict) -> dict:
        p = {k: r.get(k) for k in keep}
        p["generic_alerts"] = [a["message"] for a in r.get("generic_alerts", [])]
        p["drug_flags"] = {d["drug"]: d.get("flags") for d in r["drugs"] if d.get("flags")}
        p["snp_eligibility"] = r.get("snp_eligibility")
        p["plain_summary"] = r.get("plain_summary")
        return p

    regular = [slim(r) for r in out["results"] if not r.get("snp_type")][:top_n]
    # Explain when the list is not in order of typical-year cost (the ranking also weighs the medical max).
    ranking_notes = []
    for a, b in zip(regular, regular[1:]):
        if a["total"] > b["total"] and a.get("moop") is not None and b.get("moop") is not None and a["moop"] < b["moop"]:
            ranking_notes.append(
                (f"{a['plan_name']} aparece antes que {b['plan_name']} aunque cuesta ${a['total'] - b['total']:,.0f} más en "
                 f"un año típico, porque su límite de gastos médicos es más bajo (${a['moop']:,.0f} frente a "
                 f"${b['moop']:,.0f}): la protege mejor si tiene un año de salud difícil.") if lang == "es" else
                (f"{a['plan_name']} is listed above {b['plan_name']} even though its typical year costs "
                 f"${a['total'] - b['total']:,.0f} more, because its medical out-of-pocket max is lower "
                 f"(${a['moop']:,.0f} vs ${b['moop']:,.0f}) - safer if she has a bad health year."))
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
            "ranking_notes": ranking_notes,
            "health_usage_used": usage,
            "pharmacy_used": pharmacy,
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
                "drug_flags": "PA = prior authorization, ST = step therapy, QL = quantity limit - per plan and per "
                              "drug; never generalize one plan's rules to other plans or drugs",
                "ranking_notes": "why a plan is ranked above a cheaper one - mention in one sentence if present",
                "track_record": "PAST behavior, not a prediction: formulary_record = share of the insurer's drugs "
                                "removed or restricted 2025->2026 vs the national median, and any of HER drugs "
                                "affected; next_year = the plan's published premium/MOOP for next year. Mention "
                                "it when it separates close plans or when one of her drugs was affected.",
                "special_needs_plan_options": "C-SNP/D-SNP plans she appears eligible for; eligibility must be "
                                              "confirmed by the plan",
            },
            "assumptions": out["assumptions"]}


ALLOWED_DIRS = [ROOT / "uploads", ROOT / "evals" / "fixtures"]


def read_care_ending_notice(file_path: str, medicare_advantage: bool | None = None, lang: str = "en") -> dict:
    p = (ROOT / file_path).resolve() if not Path(file_path).is_absolute() else Path(file_path).resolve()
    if not any(str(p).startswith(str(d.resolve())) for d in ALLOWED_DIRS) or not p.exists():
        return {"error": "File not found. Ask the user to upload a photo of the notice."}
    try:
        return analyze_notice(str(p), medicare_advantage=medicare_advantage, lang=lang)
    finally:
        _discard(p)


def read_medicare_letter(file_path: str, lang: str = "en") -> dict:
    p = _safe_path(file_path)
    if not p:
        return {"error": "File not found. Ask the user to upload a photo of the letter."}
    try:
        return analyze_letter(str(p), lang=lang)
    finally:
        _discard(p)


def _safe_path(file_path: str) -> Path | None:
    p = (ROOT / file_path).resolve() if not Path(file_path).is_absolute() else Path(file_path).resolve()
    return p if any(str(p).startswith(str(d.resolve())) for d in ALLOWED_DIRS) and p.exists() else None


def _discard(p: Path) -> None:
    """Production: photos of labels/notices are deleted as soon as they are read (TRACE_LOG=0)."""
    if os.environ.get("TRACE_LOG", "1") == "0" and str(p).startswith(str((ROOT / "uploads").resolve())):
        p.unlink(missing_ok=True)


def read_medicine_label(file_path: str, lang: str = "en") -> dict:
    p = _safe_path(file_path)
    if not p:
        return {"error": "File not found. Ask the user to take a photo of the label."}
    try:
        out = analyze_label(str(p))
        for m in out.get("rxnorm_matches", []):
            m["display_name"] = friendly_name(m["rxnorm_name"], lang)
        return out
    finally:
        _discard(p)


def update_profile(person: str, lang: str = "en", **fields) -> dict:
    """No server storage: the patch is streamed to the user's device, which keeps the profile."""
    for m in fields.get("add_medicines") or []:
        if not rxnorm.exact_rxcui(m["rxnorm_name"]):
            return {"error": f"'{m['rxnorm_name']}' is not an exact RxNorm name. Call find_drug first."}
        m["display_name"] = friendly_name(m["rxnorm_name"], lang)
    patch = {"person": person, **{k: v for k, v in fields.items() if v not in (None, [], "")}}
    return {"saved_on_device": True, "patch": patch}


def check_doctor_network(doctor_name: str, state: str, organizations: list[str], city: str | None = None,
                         specialty: str | None = None) -> dict:
    return check_doctor(doctor_name, state, city, organizations, specialty)


def _match_plan(results: list[dict], query: str) -> tuple[dict | None, list[dict]]:
    """Find the plan she's in: exact plan ID first (H1019-057 / H1019-057-000), else closest plan name."""
    import difflib
    import re
    q = query.strip()
    m = re.search(r"\b([HRS]\d{4})[-_ ]?(\d{3})(?:[-_ ]?(\d{1,3}))?\b", q.upper())
    if m:
        hits = [r for r in results if r["plan_key"].startswith(f"{m.group(1)}-{m.group(2)}")]
        if len(hits) == 1 or (hits and m.group(3)):
            return hits[0], []
        if hits:
            return None, hits[:3]
    norm = lambda t: " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())  # noqa: E731
    contains = [r for r in results if norm(q) and norm(q) in norm(r["plan_name"])]
    if len({r["plan_key"] for r in contains}) == 1:
        return contains[0], []
    if len(contains) > 1:                      # e.g. "CareOne Plus" = the HMO and the HMO-POS plan
        return None, contains[:4]
    scored = sorted(((difflib.SequenceMatcher(None, norm(q), norm(r["plan_name"])).ratio(), r) for r in results),
                    key=lambda x: -x[0])
    if not scored or scored[0][0] < 0.55:
        return None, [r for _, r in scored[:3]]
    if len(scored) > 1 and scored[1][0] > scored[0][0] - 0.03 and scored[1][1]["plan_name"] != scored[0][1]["plan_name"]:
        return None, [r for _, r in scored[:3]]
    return scored[0][1], []


def check_current_plan(current_plan: str, state: str, county: str, drugs: list[dict], medicaid: bool = False,
                       chronic_conditions: list[str] | None = None, hospital_stay_last_year: bool | None = None,
                       lang: str = "en") -> dict:
    bad = [d["rxnorm_name"] for d in drugs if not rxnorm.exact_rxcui(d["rxnorm_name"])]
    if bad:
        return {"error": "Not exact RxNorm names: " + "; ".join(bad) + ". Call find_drug first."}
    usage = infer_health_usage([d["rxnorm_name"] for d in drugs], chronic_conditions, hospital_stay_last_year)
    person = {"state": state, "county": county, "medicaid": medicaid, "chronic_conditions": chronic_conditions or [],
              "health_usage": usage["level"],
              "drugs": [{"name": d["rxnorm_name"], "qty_per_30d": d["qty_per_30d"]} for d in drugs]}
    out = estimate(person, lang=lang)
    res = out["results"]
    cur, candidates = _match_plan(res, current_plan)
    if not cur:
        return {"needs_clarification": True,
                "ask": "Which of these is her plan? (Or read the plan name/ID from her member card or ANOC letter.)",
                "candidates": [{"plan_key": r["plan_key"], "plan_name": r["plan_name"], "organization": r.get("organization")}
                               for r in candidates]}
    tr = cur.get("track_record") or {}
    regular = [r for r in res if not r.get("snp_type")]
    best = next((r for r in regular if r["plan_key"] != cur["plan_key"]), None)
    rank = next((i + 1 for i, r in enumerate(res) if r["plan_key"] == cur["plan_key"]), None)
    keep = ("plan_key", "plan_name", "organization", "total", "bad_year_total", "moop", "annual_premium",
            "star_overall", "not_covered", "drug_oop_is_lower_bound", "plain_summary")
    alt = {k: best.get(k) for k in keep} if best else None
    savings = round(cur["total"] - best["total"], 2) if best else None
    return {
        "plan_year": out["year"], "data_as_of": out["data_as_of"],
        "current_plan": {**{k: cur.get(k) for k in keep}, "rank_in_county": rank, "plans_in_county": len(res)},
        "next_year": tr.get("next_year") or {"published": False,
                                             "note": "No published next-year row under this plan ID: the plan may be "
                                                     "ending or renumbered - check her Annual Notice of Change letter."},
        "track_record": tr.get("formulary_record"),
        "best_alternative": alt,
        "typical_year_savings_if_switching": savings,
        "note": "Next year's drug list (formulary) for her plan is published in October; until then her drug costs "
                "are this year's. Premium and out-of-pocket max for next year are already official.",
    }


def screen_extra_help(drugs: list[str] | None = None, **kw) -> dict:
    out = extra_help.screen(**kw)
    if drugs and out["result"] in ("likely", "possible", "automatic"):
        out["estimated_yearly_drug_cost_with_extra_help"] = extra_help.estimated_drug_cost_with_extra_help(drugs)
        out["estimate_note"] = "Rough: one fill per medicine per month at the 2026 Extra Help copays ($5.10 generic, $12.65 brand)."
    return out


IMPL = {"read_medicare_letter": read_medicare_letter, "check_current_plan": check_current_plan, "screen_extra_help": screen_extra_help, "check_doctor_network": check_doctor_network, "read_care_ending_notice": read_care_ending_notice, "read_medicine_label": read_medicine_label,
        "update_profile": update_profile, "find_drug": find_drug, "find_county": find_county, "compare_plans": compare_plans}


def call(name: str, args_json: str, lang: str = "en") -> str:
    """Run a tool. The UI language is passed to tools that produce user-facing text (never chosen by the LLM)."""
    try:
        args = json.loads(args_json or "{}")
        args.pop("lang", None)
        fn = IMPL[name]
        if "lang" in inspect.signature(fn).parameters:
            args["lang"] = lang
        return json.dumps(fn(**args), default=str)
    except Exception as e:  # tool errors go back to the model so it can recover
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
