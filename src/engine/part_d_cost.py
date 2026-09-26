"""Deterministic Part D annual out-of-pocket calculator (no LLM).

Models the post-2025 Part D design: deductible -> initial coverage -> annual OOP cap.
Simplifications (documented so the agent can disclose them):
  * one 30-day fill per drug per month, preferred retail pharmacy by default
  * gross drug cost = plan unit cost x quantity (dispensing fees ignored)
  * drugs not on formulary are reported, not priced (their cost does not count toward the cap)
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Standard Part D parameters by plan year. Plans may set a lower deductible.
PARAMS = {
    2026: {"deductible_std": 615.0, "oop_cap": 2100.0},
    2027: {"deductible_std": 700.0, "oop_cap": 2400.0},
}


@dataclass
class DrugFill:
    name: str
    unit_cost: float | None      # plan's negotiated unit cost; None -> not priced
    quantity: float              # units per 30-day fill
    on_formulary: bool
    tier: int | None = None
    cost_type: str | None = None  # "copay" | "coinsurance"
    cost_amount: float | None = None  # dollars for copay; fraction (0.25) for coinsurance
    deductible_applies: bool = True
    flags: list[str] = field(default_factory=list)  # e.g. ["PA", "ST", "QL"]


@dataclass
class PlanResult:
    plan_key: str
    annual_premium: float
    drug_oop: float
    total: float
    monthly_oop: list[float]
    not_covered: list[str]
    flags: dict[str, list[str]]
    hit_cap_month: int | None


def _cost_share(fill: DrugFill, amount: float) -> float:
    """Member cost share on `amount` of drug cost during initial coverage."""
    if fill.cost_type == "copay":
        return min(fill.cost_amount or 0.0, amount)
    if fill.cost_type == "coinsurance":
        rate = fill.cost_amount or 0.0
        if rate > 1:  # tolerate 25 meaning 25%
            rate /= 100
        return rate * amount
    return amount  # unknown cost type: conservative, member pays full


def annual_cost(plan_key: str, monthly_premium: float, plan_deductible: float,
                fills: list[DrugFill], year: int = 2026, months: int = 12) -> PlanResult:
    cap = PARAMS[year]["oop_cap"]
    ded_left = min(plan_deductible, PARAMS[year]["deductible_std"])
    oop = 0.0
    monthly: list[float] = []
    hit_cap_month = None
    not_covered = [f.name for f in fills if not f.on_formulary or f.unit_cost is None]
    for m in range(1, months + 1):
        month_pay = 0.0
        for f in fills:
            if not f.on_formulary or f.unit_cost is None:
                continue
            gross = f.unit_cost * f.quantity
            if oop >= cap:
                pay = 0.0
            else:
                pay = 0.0
                rest = gross
                if f.deductible_applies and ded_left > 0:
                    d = min(rest, ded_left)
                    pay += d
                    ded_left -= d
                    rest -= d
                if rest > 0:
                    pay += _cost_share(f, rest)
                pay = min(pay, cap - oop)
            oop += pay
            month_pay += pay
        if hit_cap_month is None and oop >= cap - 1e-9:
            hit_cap_month = m
        monthly.append(round(month_pay, 2))
    premium = monthly_premium * months
    return PlanResult(plan_key, round(premium, 2), round(oop, 2), round(premium + oop, 2),
                      monthly, not_covered, {f.name: f.flags for f in fills if f.flags}, hit_cap_month)
