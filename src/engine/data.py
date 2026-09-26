"""Read-only access to the CMS Part D public use file loaded in data/processed/partd.duckdb.

All SQL lives here so the agent tools never touch the database directly.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "processed" / "partd.duckdb"

# plan_info.SNP codes in the CMS file
SNP_TYPES = {"0": None, "1": "C-SNP", "2": "D-SNP", "3": "I-SNP"}
# bene_cost COST_TYPE codes: 0 = not offered at this pharmacy type, 1 = copay, 2 = coinsurance
COST_TYPES = {"1": "copay", "2": "coinsurance"}
PHARMACY_COLUMNS = {
    "preferred_retail": ("cost_type_pref", "cost_amt_pref"),
    "standard_retail": ("cost_type_nonpref", "cost_amt_nonpref"),
    "preferred_mail": ("cost_type_mail_pref", "cost_amt_mail_pref"),
    "standard_mail": ("cost_type_mail_nonpref", "cost_amt_mail_nonpref"),
}
# if a plan does not offer the requested pharmacy type, try these next
PHARMACY_FALLBACK = {
    "preferred_retail": ["preferred_retail", "standard_retail"],
    "standard_retail": ["standard_retail"],
    "preferred_mail": ["preferred_mail", "standard_mail"],
    "standard_mail": ["standard_mail"],
}


@dataclass
class Plan:
    contract_id: str
    plan_id: str
    segment_id: str
    name: str
    formulary_id: str
    monthly_premium: float
    drug_deductible: float
    snp_type: str | None  # None, "C-SNP", "D-SNP", "I-SNP"

    @property
    def key(self) -> str:
        return f"{self.contract_id}-{self.plan_id}-{self.segment_id}"

    @property
    def is_pdp(self) -> bool:
        return self.contract_id.startswith("S")


@dataclass
class FormularyEntry:
    tier: int
    representative_ndc: str | None
    flags: list[str]


@dataclass
class CostShare:
    cost_type: str | None
    amount: float | None
    deductible_applies: bool
    pharmacy_used: str | None


def connect(db: Path = DEFAULT_DB):
    import duckdb

    if not db.exists():
        raise FileNotFoundError(f"{db} not found. Run notebooks/day2_01_download_spuf.py first.")
    return duckdb.connect(str(db), read_only=True)


def plans(con) -> list[Plan]:
    rows = con.execute("""
        SELECT DISTINCT contract_id, plan_id, segment_id, plan_name, formulary_id,
               coalesce(try_cast(premium AS DOUBLE), 0), coalesce(try_cast(deductible AS DOUBLE), 0),
               coalesce(trim(snp), '0')
        FROM miami_plans
    """).fetchall()
    return [Plan(c, p, s, n, f, prem, ded, SNP_TYPES.get(snp)) for c, p, s, n, f, prem, ded, snp in rows]


def formulary_entry(con, formulary_id: str, rxcui: str) -> FormularyEntry | None:
    row = con.execute("""
        SELECT try_cast(tier_level_value AS INT), ndc,
               prior_authorization_yn, step_therapy_yn, quantity_limit_yn
        FROM formulary WHERE formulary_id = ? AND rxcui = ?
        ORDER BY 1 LIMIT 1
    """, [formulary_id, rxcui]).fetchone()
    if not row:
        return None
    tier, ndc, pa, st, ql = row
    flags = [k for k, v in (("PA", pa), ("ST", st), ("QL", ql)) if (v or "").upper() == "Y"]
    return FormularyEntry(tier, (ndc or "").strip() or None, flags)


def unit_cost(con, plan: Plan, representative_ndc: str | None, all_ndcs: list[str]) -> tuple[float | None, str]:
    """Plan's negotiated 30-day unit cost. Prefer CMS's representative NDC; else median over all NDCs."""
    base = """
        SELECT try_cast(unit_cost AS DOUBLE) FROM pricing
        WHERE contract_id = ? AND plan_id = ? AND segment_id = ? AND days_supply IN ('30', '030', '1')
    """
    if representative_ndc:
        row = con.execute(base + " AND ndc = ?", [plan.contract_id, plan.plan_id, plan.segment_id,
                                                   representative_ndc]).fetchone()
        if row and row[0] is not None:
            return row[0], "representative_ndc"
    costs = [r[0] for r in con.execute(base + " AND ndc IN (SELECT unnest(?::VARCHAR[]))",
                                       [plan.contract_id, plan.plan_id, plan.segment_id, all_ndcs]).fetchall()
             if r[0] is not None]
    if costs:
        return statistics.median(costs), "median_ndc"
    return None, "not_priced"


def cost_share(con, plan: Plan, tier: int, pharmacy: str = "preferred_retail") -> CostShare:
    for ph in PHARMACY_FALLBACK[pharmacy]:
        tcol, acol = PHARMACY_COLUMNS[ph]
        row = con.execute(f"""
            SELECT {tcol}, try_cast({acol} AS DOUBLE), ded_applies_yn FROM bene_cost
            WHERE contract_id = ? AND plan_id = ? AND segment_id = ?
              AND coverage_level = '1' AND try_cast(tier AS INT) = ? AND days_supply = '1'
            LIMIT 1
        """, [plan.contract_id, plan.plan_id, plan.segment_id, tier]).fetchone()
        if row and str(row[0]) in COST_TYPES:
            return CostShare(COST_TYPES[str(row[0])], row[1], (row[2] or "Y").upper() == "Y", ph)
    return CostShare(None, None, True, None)
