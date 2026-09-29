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


MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
SERVICE_TYPES_ES = {"snf": "la atención en un centro de enfermería especializada", "home_health": "la atención médica en el hogar",
                    "hospice": "los cuidados paliativos (hospicio)", "corf": "la rehabilitación ambulatoria (CORF)"}


def _date(d: date, lang: str) -> str:
    return f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}" if lang == "es" else f"{d:%B %-d, %Y}"


def _texts(lang: str, *, who, svc, qio, provider, eff, ma):
    """All user-facing wording in one place. Spanish follows Medicare's own Spanish terms
    (Aviso de No Cobertura de Medicare, apelación inmediata, Organización para el Mejoramiento de la Calidad)."""
    if lang == "es":
        decision = ("La QIO generalmente decide antes de la fecha de vigencia del aviso (plan de salud de Medicare)."
                    if ma else "La QIO generalmente decide a más tardar dos días después de la fecha de vigencia del aviso.")
        script = [
            f"Llame ahora a {qio}. Diga: 'Quiero una apelación inmediata (acelerada) de un Aviso de No Cobertura de Medicare.'",
            f"Dé: el nombre de {who}, su número de Medicare, el proveedor{(' (' + provider + ')') if provider else ''}, "
            f"que {svc} termina el {eff}, y el nombre del plan.",
            "Explique por qué la atención debe continuar (por ejemplo, todavía necesita enfermería o terapia especializada "
            "todos los días; no es seguro volver a casa todavía).",
            "Anote la fecha, la hora, el nombre de la persona con quien habló y cualquier número de referencia.",
        ]
        checklist = [
            "Pida al proveedor la Explicación Detallada de No Cobertura (DENC); deben entregarla después de que se contacte a la QIO.",
            "Pida al proveedor una copia de los expedientes que envían a la QIO.",
            f"Pida al médico de {who} que llame o escriba a la QIO explicando por qué todavía necesita atención especializada diaria.",
            "Recuerde: la cobertura NO depende de 'mejorar'. La atención especializada para mantener su condición o frenar "
            "el deterioro puede estar cubierta. 'Se estancó' o 'solo mantenimiento' no es por sí solo una razón válida para parar.",
            "Guarde el aviso y todos los papeles juntos; anote cada llamada.",
        ]
        if_missed = [
            "Es posible que todavía tenga derecho a apelar; el aviso lo explica.",
            ("En un plan Medicare Advantage: pida al plan de inmediato una reconsideración acelerada."
             if ma else "En Medicare Original: todavía puede pedírselo a la QIO, pero podría tener que pagar si la "
                        "atención continúa y la apelación no prospera."),
            "Llame al 1-800-MEDICARE o a su programa SHIP local para recibir ayuda gratuita.",
        ]
        nxt = [
            "Los servicios continúan mientras la QIO revisa el caso.",
            decision,
            "Si la QIO decide que la atención termina demasiado pronto, la cobertura puede continuar (se aplican los copagos habituales).",
            "Si la QIO dice que no, puede pedir el siguiente nivel de apelación; la carta de decisión explica cómo y cuándo.",
        ]
        return decision, script, checklist, if_missed, nxt
    decision = ("The QIO generally decides by the effective date on the notice (Medicare health plan)."
                if ma else "The QIO generally decides no later than two days after the effective date on the notice.")
    script = [
        f"Call {qio} now. Say: 'I want an immediate (fast-track) appeal of a Notice of Medicare Non-Coverage.'",
        f"Give: {who}'s name, Medicare number, the provider{(' (' + provider + ')') if provider else ''}, "
        f"that {svc} is ending on {eff}, and the plan name.",
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
         if ma else "In Original Medicare: you can still ask the QIO, but you may have to pay if care continues and the appeal fails."),
        "Call 1-800-MEDICARE or your local SHIP for free help.",
    ]
    nxt = [
        "Services continue while the QIO reviews.",
        decision,
        "If the QIO agrees care is ending too soon, coverage can continue (usual copays apply).",
        "If the QIO says no, you can ask for the next level of appeal - the decision letter explains how and by when.",
    ]
    return decision, script, checklist, if_missed, nxt


def plan_appeal(effective: date, now: datetime, service: str = "snf", medicare_advantage: bool = True,
                notice_received: date | None = None, qio_name: str | None = None, qio_phone: str | None = None,
                provider: str | None = None, patient_first_name: str | None = None,
                tz: str = "America/New_York", lang: str = "en") -> AppealPlan:
    dl = deadline_for(effective, tz)
    now = now.astimezone(ZoneInfo(tz))
    hours = (dl - now).total_seconds() / 3600
    status = "missed" if hours < 0 else ("urgent" if hours <= 24 else "on_time")
    late = None if notice_received is None else (effective - notice_received).days < 2
    es = lang == "es"
    who = patient_first_name or ("la persona" if es else "the patient")
    svc = (SERVICE_TYPES_ES if es else SERVICE_TYPES).get(service, "la atención" if es else "care")
    qio = f"{qio_name or ('la QIO que aparece en el aviso' if es else 'the QIO listed on the notice')} " \
          f"({qio_phone or ('el teléfono del aviso' if es else 'phone number on the notice')})"
    decision, call_script, checklist, if_missed, next_steps = _texts(
        lang, who=who, svc=svc, qio=qio, provider=provider, eff=_date(effective, lang), ma=medicare_advantage)
    d = dl.date()
    deadline = (f"{DAYS_ES[d.weekday()]}, {_date(d, 'es')} a las 12:00 del mediodía {dl:%Z}" if es
                else dl.strftime("%A, %B %-d, %Y at 12:00 noon %Z"))
    return AppealPlan(effective.isoformat(), deadline, round(hours, 1),
                      status, late, decision, call_script, checklist, if_missed, next_steps)
