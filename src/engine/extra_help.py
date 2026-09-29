"""Extra Help (Part D Low-Income Subsidy) screening - a quick "you may qualify" check, never a determination.

2026 limits (people who don't already have Medicaid/SSI/MSP):
  income  < 150% of the federal poverty level: $24,180/yr single, $32,700/yr married (48 states + DC);
          Alaska $30,165 / $40,815; Hawaii $27,780 / $37,575          - NCOA 2026 LIS chart (Feb 2026)
  resources <= $18,090 single, $36,100 married (includes $1,500 pp burial allowance)  - CMS CY2026 LIS memo
  2026 cost sharing with Extra Help: $0 deductible, at most $5.10 generic / $12.65 brand per fill,
  $0 after the out-of-pocket cap                                     - CMS CY2026 LIS memo
People with Medicaid, SSI or a Medicare Savings Program get Extra Help automatically.
Social Security decides eligibility (countable income has disregards, e.g. $20/month general).
"""
from __future__ import annotations

YEAR = 2026
INCOME = {"default": (24180, 32700), "alaska": (30165, 40815), "hawaii": (27780, 37575)}
RESOURCES = (18090, 36100)
COPAY_GENERIC, COPAY_BRAND = 5.10, 12.65
OOP_CAP = 2100.0
SOURCES = ["https://www.cms.gov/files/document/cy2026-lis-resource-limits-memo.pdf",
           "https://www.ncoa.org (2026 Part D LIS eligibility and benefits chart)"]
APPLY = {"online": "https://www.ssa.gov/medicare/part-d-extra-help", "phone": "1-800-772-1213 (Social Security)"}


def screen(married: bool = False, state: str | None = None, yearly_income: float | None = None,
           resources: float | None = None, has_medicaid_ssi_or_msp: bool = False) -> dict:
    i = 1 if married else 0
    region = (state or "").strip().lower()
    inc_limit = INCOME.get(region, INCOME["default"])[i]
    res_limit = RESOURCES[i]
    out = {"year": YEAR, "income_limit_per_year": inc_limit, "resource_limit": res_limit,
           "not_counted_as_resources": ["the home she lives in", "one car", "personal belongings",
                                        "life insurance policies", "burial plots"],
           "apply": APPLY, "sources": SOURCES,
           "note": "A quick screen, not a decision. Social Security decides; some income is not counted."}
    if has_medicaid_ssi_or_msp:
        return {**out, "result": "automatic", "explain": "People with Medicaid, SSI or a Medicare Savings Program get "
                                                         "Extra Help automatically; no application needed."}
    if yearly_income is None or resources is None:
        return {**out, "result": "need_info", "explain": "Need yearly income and savings (resources) to screen."}
    inc_ok = yearly_income <= inc_limit
    inc_close = yearly_income <= inc_limit * 1.10    # disregards can bring countable income under the limit
    res_ok = resources <= res_limit
    if inc_ok and res_ok:
        result, why = "likely", "Income and savings are under the 2026 limits."
    elif inc_close and res_ok:
        result, why = "possible", "Income is just over the limit; some income isn't counted, so it's worth applying."
    else:
        result = "unlikely"
        why = ("Income is over the limit. " if not inc_close else "") + ("Savings are over the limit." if not res_ok else "")
    return {**out, "result": result, "explain": why.strip()}


def estimated_drug_cost_with_extra_help(drug_names: list[str], fills_per_year: int = 12) -> float:
    """Rough yearly drug cost with Extra Help: one fill per drug per month at the 2026 LIS copays, capped."""
    per_month = sum(COPAY_BRAND if "[" in n else COPAY_GENERIC for n in drug_names)
    return round(min(per_month * fills_per_year, OOP_CAP), 2)
