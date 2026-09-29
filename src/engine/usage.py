"""Estimate how much health care someone uses (low / medium / high) from what we already know,
instead of asking an 80-year-old to rate herself. Transparent: always returns the reasons."""
from __future__ import annotations

HIGH_CONDITIONS = ["heart failure", "chf", "copd", "emphysema", "dialysis", "kidney failure", "esrd", "end-stage renal",
                   "cancer", "chemotherapy", "stroke", "dementia", "alzheimer", "parkinson", "amyotrophic", "transplant",
                   "hiv", "cirrhosis", "multiple sclerosis"]
CHRONIC_WORDS = ["diabetes", "hypertension", "high blood pressure", "afib", "atrial fibrillation", "coronary",
                 "arthritis", "osteoporosis", "asthma", "depression", "kidney disease", "ckd", "thyroid",
                 "cholesterol", "glaucoma"]
SPECIALTY_HINTS = ["insulin", "pen injector", "auto-injector", "syringe", "inhal", "enzalutamide", "lenalidomide", "adalimumab",
                   "ibrutinib", "apixaban", "rivaroxaban", "sacubitril"]


def infer_health_usage(drug_names: list[str], conditions: list[str] | None = None,
                       hospital_stay_last_year: bool | None = None,
                       specialist_visits_per_year: int | None = None) -> dict:
    conditions = [c.lower() for c in (conditions or [])]
    names = [d.lower() for d in drug_names]
    reasons, level = [], "low"

    serious = sorted({h for h in HIGH_CONDITIONS for c in conditions if h in c})
    chronic = sorted({w for w in CHRONIC_WORDS for c in conditions if w in c})
    injectables = [n for n in names if any(h in n for h in SPECIALTY_HINTS)]

    if hospital_stay_last_year:
        level = "high"; reasons.append("a hospital stay in the past year")
    if serious:
        level = "high"; reasons.append("a serious condition (" + ", ".join(serious) + ")")
    if specialist_visits_per_year is not None and specialist_visits_per_year >= 8:
        level = "high"; reasons.append(f"about {specialist_visits_per_year} specialist visits a year")
    if level != "high":
        if len(names) >= 5:
            level = "medium"; reasons.append(f"{len(names)} regular medicines")
        if len(chronic) >= 2:
            level = "medium"; reasons.append("more than one ongoing condition")
        if injectables:
            level = "medium"; reasons.append("medicines that usually mean regular doctor follow-up")
    if not reasons:
        reasons.append(f"{len(names)} regular medicine(s) and no hospital stay or serious condition mentioned")
    return {"level": level, "reasons": reasons,
            "explain": f"I estimated {level} health care use because of " + "; ".join(reasons) + "."}
