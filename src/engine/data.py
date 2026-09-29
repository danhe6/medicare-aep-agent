"""Read-only access to the current CMS data release (data/releases/CURRENT -> Parquet files).

National data; each connection is scoped to one market (state + county) with load_market(),
which materializes that county's plans, formularies, cost sharing and prices as small temp tables.
All SQL lives here so agent tools never touch the data directly.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

RELEASES = Path(__file__).resolve().parents[2] / "data" / "releases"
TABLES = ("plan_info", "geo", "formulary", "bene_cost", "insulin_cost", "pricing", "landscape", "mfp")

SNP_TYPES = {"0": None, "1": "C-SNP", "2": "D-SNP", "3": "I-SNP"}
COST_TYPES = {"1": "copay", "2": "coinsurance"}  # 0 = not offered at this pharmacy type
PHARMACY_COLUMNS = {
    "preferred_retail": ("cost_type_pref", "cost_amt_pref"),
    "standard_retail": ("cost_type_nonpref", "cost_amt_nonpref"),
    "preferred_mail": ("cost_type_mail_pref", "cost_amt_mail_pref"),
    "standard_mail": ("cost_type_mail_nonpref", "cost_amt_mail_nonpref"),
}
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
    snp_type: str | None
    moop: float | None = None            # in-network medical out-of-pocket max (MA only)
    star_overall: float | None = None
    star_part_d: float | None = None
    organization: str | None = None
    plan_type: str | None = None
    csnp_condition: str | None = None

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


# ---------------------------------------------------------------- release + market
def current_release() -> Path:
    ptr = RELEASES / "CURRENT"
    if not ptr.exists():
        raise FileNotFoundError("No data release yet. Run: python pipeline/build.py")
    return RELEASES / ptr.read_text().strip()


def manifest(release: Path | None = None) -> dict:
    return json.loads(((release or current_release()) / "manifest.json").read_text())


def connect(release: Path | None = None):
    import duckdb

    rel = release or current_release()
    con = duckdb.connect()
    for t in TABLES:
        f = rel / (t + ".parquet")
        if f.exists():  # landscape is optional in older releases
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{f}')")
    return con


def counties(con, state: str | None = None) -> list[tuple[str, str]]:
    q = "SELECT DISTINCT statename, county FROM geo"
    args = []
    if state:
        q += " WHERE lower(statename) = lower(?)"
        args.append(state)
    return con.execute(q + " ORDER BY 1, 2", args).fetchall()


def load_market(con, state: str, county: str) -> int:
    """Scope this connection to one county. Returns the number of plans offered there."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE market_plans AS
        WITH g AS (
            SELECT county_code, trim(pdp_region_code) AS pdp_region_code FROM geo
            WHERE lower(statename) = lower(?) AND lower(county) = lower(?)
        )
        SELECT DISTINCT p.* FROM plan_info p, g
        WHERE (trim(p.county_code) = g.county_code
               OR (p.contract_id LIKE 'S%' AND trim(p.pdp_region_code) = g.pdp_region_code))
          AND coalesce(p.plan_suppressed_yn, 'N') <> 'Y'
    """, [state, county])
    n = con.execute("SELECT count(*) FROM market_plans").fetchone()[0]
    if n == 0:
        raise LookupError(f"No plans found for {county}, {state}. Check spelling with data.counties().")
    has_land = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'landscape'").fetchone()[0]
    if has_land:
        con.execute("""CREATE OR REPLACE TEMP TABLE market_landscape AS
            SELECT DISTINCT ON (contract_id, plan_id, segment_id) * FROM landscape
            WHERE lower(state) = lower(?) AND lower(county) = lower(?)
               OR (contract_id LIKE 'S%' AND lower(state) = lower(?))""", [state, county, state])
    else:
        con.execute("""CREATE OR REPLACE TEMP TABLE market_landscape AS
            SELECT NULL::VARCHAR contract_id, NULL::VARCHAR plan_id, NULL::VARCHAR segment_id,
                   NULL::DOUBLE moop, NULL::DOUBLE star_overall, NULL::DOUBLE star_part_d,
                   NULL::DOUBLE total_monthly_premium, NULL::VARCHAR organization_marketing_name,
                   NULL::VARCHAR plan_type, NULL::VARCHAR csnp_condition WHERE false""")
    con.execute("""CREATE OR REPLACE TEMP TABLE market_formulary AS
        SELECT * FROM formulary WHERE formulary_id IN (SELECT DISTINCT formulary_id FROM market_plans)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE market_bene_cost AS
        SELECT b.* FROM bene_cost b JOIN (SELECT DISTINCT contract_id, plan_id, segment_id FROM market_plans) m
        USING (contract_id, plan_id, segment_id)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE market_insulin_cost AS
        SELECT i.* FROM insulin_cost i JOIN (SELECT DISTINCT contract_id, plan_id, segment_id FROM market_plans) m
        USING (contract_id, plan_id, segment_id)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE market_pricing AS
        SELECT pr.* FROM pricing pr JOIN (SELECT DISTINCT contract_id, plan_id FROM market_plans) m
        USING (contract_id, plan_id)
        WHERE pr.days_supply IN ('30', '030', '1')""")
    return n


# ---------------------------------------------------------------- queries (market-scoped)
def plans(con) -> list[Plan]:
    rows = con.execute("""
        SELECT DISTINCT p.contract_id, p.plan_id, p.segment_id, p.plan_name, p.formulary_id,
               coalesce(l.total_monthly_premium, try_cast(p.premium AS DOUBLE), 0),
               coalesce(try_cast(p.deductible AS DOUBLE), 0), coalesce(trim(p.snp), '0'),
               l.moop, l.star_overall, l.star_part_d, l.organization_marketing_name, l.plan_type, l.csnp_condition
        FROM market_plans p
        LEFT JOIN market_landscape l USING (contract_id, plan_id, segment_id)
    """).fetchall()
    return [Plan(c, p, s, n, f, prem, ded, SNP_TYPES.get(snp), moop, star, stard, org, ptype, cond)
            for c, p, s, n, f, prem, ded, snp, moop, star, stard, org, ptype, cond in rows]


def formulary_entry(con, formulary_id: str, rxcuis: str | list[str]) -> FormularyEntry | None:
    """First formulary row matching any of the given RXCUIs (the drug and its equivalent forms)."""
    ids = [rxcuis] if isinstance(rxcuis, str) else [r for r in rxcuis if r]
    row = con.execute("""
        SELECT try_cast(tier_level_value AS INT), ndc, prior_authorization_yn, step_therapy_yn, quantity_limit_yn
        FROM market_formulary WHERE formulary_id = ? AND rxcui IN (SELECT unnest(?::VARCHAR[]))
        ORDER BY 1 LIMIT 1
    """, [formulary_id, ids]).fetchone()
    if not row:
        return None
    tier, ndc, pa, st, ql = row
    flags = [k for k, v in (("PA", pa), ("ST", st), ("QL", ql)) if (v or "").upper() == "Y"]
    return FormularyEntry(tier, (ndc or "").strip() or None, flags)


def unit_cost(con, plan: Plan, representative_ndc: str | None, all_ndcs: list[str]) -> tuple[float | None, str]:
    """Plan's negotiated unit cost. Prefer CMS's representative NDC; else median over all NDCs."""
    base = "SELECT try_cast(unit_cost AS DOUBLE) FROM market_pricing WHERE contract_id = ? AND plan_id = ? AND segment_id = ?"
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


def negotiated_unit_price(con, ndcs: list[str], on: str) -> tuple[float, str] | None:
    """Medicare's negotiated price (IRA "maximum fair price") in effect on date `on` (YYYY-MM-DD) for any of these
    NDC-11s, from CMS's official file. None when the drug isn't negotiated or the release has no mfp table."""
    ndcs = [n for n in ndcs if n]
    if not ndcs:
        return None
    try:
        row = con.execute("""SELECT unit_price, drug FROM mfp
                             WHERE ndc IN (SELECT unnest(?::VARCHAR[])) AND start_date <= CAST(? AS DATE)
                               AND (end_date IS NULL OR end_date >= CAST(? AS DATE))
                             ORDER BY start_date DESC LIMIT 1""", [ndcs, on, on]).fetchone()
    except Exception:          # older release without mfp.parquet
        return None
    return (float(row[0]), row[1]) if row else None


def market_unit_cost(con, representative_ndc: str | None, all_ndcs: list[str]) -> float | None:
    """Typical negotiated unit price for a drug a plan does NOT cover.

    Tries this market first, then the national price table (a brand every local plan dropped, e.g. after
    its generic launched, has no local prices). Representative NDC first, then any NDC of the drug.
    """
    tries = [[representative_ndc]] if representative_ndc else []
    tries.append(all_ndcs)
    for table in ("market_pricing", "pricing"):
        for ndcs in tries:
            if not ndcs:
                continue
            row = con.execute(f"""SELECT median(try_cast(unit_cost AS DOUBLE)) FROM {table}
                                  WHERE ndc IN (SELECT unnest(?::VARCHAR[]))
                                    AND days_supply IN ('30', '030', '1')""", [ndcs]).fetchone()
            if row and row[0] is not None:
                return row[0]
    return None


def cost_share(con, plan: Plan, tier: int, pharmacy: str = "preferred_retail") -> CostShare:
    for ph in PHARMACY_FALLBACK[pharmacy]:
        tcol, acol = PHARMACY_COLUMNS[ph]
        row = con.execute(f"""
            SELECT {tcol}, try_cast({acol} AS DOUBLE), ded_applies_yn FROM market_bene_cost
            WHERE contract_id = ? AND plan_id = ? AND segment_id = ?
              AND coverage_level = '1' AND try_cast(tier AS INT) = ? AND days_supply = '1'
            LIMIT 1
        """, [plan.contract_id, plan.plan_id, plan.segment_id, tier]).fetchone()
        if row and str(row[0]) in COST_TYPES:
            return CostShare(COST_TYPES[str(row[0])], row[1], (row[2] or "Y").upper() == "Y", ph)
    return CostShare(None, None, True, None)


INSULIN_CAP = 35.0  # IRA: covered insulin costs at most $35 per month's supply, no deductible
INSULIN_COLUMNS = {
    "preferred_retail": ("copay_amt_pref_insln", "coin_amt_pref_insln"),
    "standard_retail": ("copay_amt_nonpref_insln", "coin_amt_nonpref_insln"),
    "preferred_mail": ("copay_amt_mail_pref_insln", "coin_amt_mail_pref_insln"),
    "standard_mail": ("copay_amt_mail_nonpref_insln", "coin_amt_mail_nonpref_insln"),
}


def insulin_cost_share(con, plan: Plan, tier: int, pharmacy: str = "preferred_retail") -> CostShare:
    """Plan's insulin-specific cost sharing; the $35/month cap is applied by the engine."""
    for ph in PHARMACY_FALLBACK[pharmacy]:
        ccol, icol = INSULIN_COLUMNS[ph]
        row = con.execute(f"""
            SELECT try_cast(trim({ccol}) AS DOUBLE), try_cast(trim({icol}) AS DOUBLE) FROM market_insulin_cost
            WHERE contract_id = ? AND plan_id = ? AND segment_id = ?
              AND try_cast(tier AS INT) = ? AND days_supply = '1' LIMIT 1
        """, [plan.contract_id, plan.plan_id, plan.segment_id, tier]).fetchone()
        if row and row[0] is not None:
            return CostShare("copay", min(row[0], INSULIN_CAP), False, ph)
        if row and row[1] is not None:
            return CostShare("coinsurance_capped", row[1], False, ph)
    return CostShare("copay", INSULIN_CAP, False, None)  # conservative: the legal maximum
