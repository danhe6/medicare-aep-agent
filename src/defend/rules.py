"""Fast-track ("immediate") appeal rules when skilled nursing, home health, hospice or CORF care is ending.

Deterministic - no LLM. Source: the standard CMS Notice of Medicare Non-Coverage (form CMS-10123) and
Medicare.gov "Fast appeals". Key rule: ask the BFCC-QIO for an appeal no later than NOON of the day BEFORE
the effective (last covered) date printed on the notice.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SERVICE_TYPES = {
    "snf": "skilled nursing facility care",
    "home_health": "home health care",
    "hospice": "hospice care",
    "corf": "outpatient rehabilitation (CORF) care",
}
SOURCES = [
    "CMS Notice of Medicare Non-Coverage, form CMS-10123",
    "https://www.medicare.gov/providers-services/claims-appeals-complaints/appeals/fast-appeals",
]


@dataclass
class AppealPlan:
    effective_date: str               # last day covered, from the notice
    deadline_local: str               # noon the day before, local time
    hours_left: float                 # negative = deadline passed
    status: str                       # "on_time" | "urgent" | "missed"
    notice_was_late: bool | None      # notice delivered < 2 days before the effective date
    decision_expected: str
    call_script: list[str]
    checklist: list[str]
    if_missed: list[str]
    what_happens_next: list[str]
    sources: list[str] = field(default_factory=lambda: list(SOURCES))

    def to_dict(self) -> dict:
        return asdict(self)


def deadline_for(effective: date, tz: str = "America/New_York") -> datetime:
    return datetime.combine(effective - timedelta(days=1), time(12, 0), ZoneInfo(tz))


def plan_appeal(effective: date, now: datetime, service: str = "snf", medicare_advantage: bool = True,
                notice_received: date | None = None, qio_name: str | None = None, qio_phone: str | None = None,
                provider: str | None = None, patient_first_name: str | None = None,
                tz: str = "America/New_York") -> AppealPlan:
    dl = deadline_for(effective, tz)
    now = now.astimezone(ZoneInfo(tz))
    hours = (dl - now).total_seconds() / 3600
    status = "missed" if hours < 0 else ("urgent" if hours <= 24 else "on_time")
    late = None if notice_received is None else (effective - notice_received).days < 2
    who = patient_first_name or "the patient"
    svc = SERVICE_TYPES.get(service, "care")
    qio = f"{qio_name or 'the QIO listed on the notice'} ({qio_phone or 'phone number on the notice'})"
    decision = ("The QIO generally decides by the effective date on the notice (Medicare health plan)."
                if medicare_advantage else
                "The QIO generally decides no later than two days after the effective date on the notice.")
    call_script = [
        f"Call {qio} now. Say: 'I want an immediate (fast-track) appeal of a Notice of Medicare Non-Coverage.'",
        f"Give: {who}'s name, Medicare number, the provider{(' (' + provider + ')') if provider else ''}, "
        f"that {svc} is ending on {effective:%B %-d, %Y}, and the plan name.",
        "Say why care should continue (e.g. still needs daily skilled nursing or therapy; not safe at home yet).",
        "Write down the date, time, the name of the person you spoke with, and any reference number.",
    ]
    checklist = [
        "Ask the provider for the Detailed Explanation of Non-Coverage (DENC); they must give it after the QIO is contacted.",
        "Ask the provider for a copy of the records they send to the QIO.",
        f"Ask {who}'s doctor to call or write to the QIO explaining why daily skilled care is still needed.",
        "Remember: coverage does NOT depend on 'improving' - skilled care to maintain her condition or slow "
        "decline can be covered. 'Plateaued' or 'maintenance only' is not by itself a valid reason to stop.",
        "Keep the notice and all papers together; note every call.",
    ]
    if_missed = [
        "You may still have appeal rights - the notice says so.",
        ("In a Medicare Advantage plan: ask the plan right away for an expedited (fast) reconsideration."
         if medicare_advantage else
         "In Original Medicare: you can still ask the QIO, but you may have to pay if care continues and the appeal fails."),
        "Call 1-800-MEDICARE or your local SHIP for free help.",
    ]
    next_steps = [
        "Services continue while the QIO reviews.",
        decision,
        "If the QIO agrees care is ending too soon, coverage can continue (usual copays apply).",
        "If the QIO says no, you can ask for the next level of appeal - the decision letter explains how and by when.",
    ]
    return AppealPlan(effective.isoformat(), dl.strftime("%A, %B %-d, %Y at 12:00 noon %Z"), round(hours, 1),
                      status, late, decision, call_script, checklist, if_missed, next_steps)
