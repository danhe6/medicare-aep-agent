"""Deadlines and next steps per letter type. Deterministic, no LLM. Sources are listed per type and shown to users.

Checked 2026-10-09 against Medicare.gov / SSA:
  * Part D drug denial  -> redetermination within 65 days of the notice date; plan decides in 7 days (benefit),
    14 days (payment), 72 hours if fast. Exceptions need a prescriber statement.
  * Medicare Advantage denial -> reconsideration within 65 days of the notice date; plan decides in 30 days
    (pre-service), 60 days (payment), 7 days (Part B drug), 72 hours if fast.
  * Original Medicare (Medicare Summary Notice) -> redetermination by the date printed on the MSN, form CMS-20027,
    to the Medicare contractor on the MSN's last page; decision usually within 60 days.
  * IRMAA (Social Security) -> reconsideration within 60 days of receipt (receipt = notice date + 5 days), form
    SSA-561; a life-changing event (retirement, death of a spouse...) is a new determination with form SSA-44.
"""
from __future__ import annotations

from datetime import date, timedelta

SOURCES = {
    "partd_denial": ["https://www.medicare.gov/providers-services/claims-appeals-complaints/appeals/drug-plans"],
    "ma_denial": ["https://www.medicare.gov/providers-services/claims-appeals-complaints/appeals/medicare-health-plans"],
    "msn": ["https://www.medicare.gov/providers-services/claims-appeals-complaints/appeals/original-medicare"],
    "irmaa": ["https://secure.ssa.gov/poms.nsf/lnx/0601140001"],
}

LATE = {
    "en": "The deadline has passed, but you can still ask for a late appeal if you had \"good cause\": in the letter, "
          "explain the real reason you are late (they decide whether to accept it). Only give a reason that is true.",
    "es": "La fecha límite ya pasó, pero aún puede pedir una apelación tardía si tuvo \"causa justificada\": en la carta "
          "explique la razón real del retraso (ellos deciden si la aceptan). Dé solo una razón que sea verdad.",
}

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]


def fmt(d: date | None, lang: str = "en") -> str | None:
    if not d:
        return None
    return f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}" if lang == "es" else f"{d:%B %-d, %Y}"


def _deadline(d: date | None, today: date, lang: str) -> dict | None:
    if not d:
        return None
    left = (d - today).days
    return {"date": d.isoformat(), "date_text": fmt(d, lang), "days_left": left,
            "status": "missed" if left < 0 else "urgent" if left <= 7 else "on_time"}


T = {
    "en": {
        "titles": {"partd_denial": "Drug coverage denied", "ma_denial": "Medical coverage denied",
                   "msn": "Medicare Summary Notice (a statement, not a bill)", "irmaa": "Higher Part B / D premium (IRMAA)",
                   "anoc": "Annual Notice of Change (your plan next year)", "nomnc": "Care is ending (Notice of Medicare Non-Coverage)",
                   "eob": "Explanation of Benefits (a statement, not a bill)", "bill": "A bill from a doctor or hospital", "other": "Medicare letter"},
        "partd": ["Ask the doctor who prescribed it to send the plan a supporting statement explaining why you need this drug "
                  "(required for an exception). You can use the request below.",
                  "Send the plan a \"Request for Redetermination\" (the letter below works) by mail, fax or phone, using the "
                  "contact on the denial notice.",
                  "If waiting could seriously harm your health, ask for a FAST appeal: the plan must decide within 72 hours.",
                  "Keep a copy and write down the date you sent it."],
        "partd_time": "The plan must decide within 7 days (72 hours if fast; 14 days if you already paid and want money back).",
        "ma": ["Ask your doctor for a short letter or records showing why you need this care. You can use the request below.",
               "Send the plan a request for \"reconsideration\" (the letter below works), using the contact on the denial notice.",
               "If waiting could seriously harm your health, ask for a FAST appeal: the plan must decide within 72 hours. "
               "If your doctor asks for it, the plan must give it.",
               "Keep a copy and write down the date you sent it."],
        "ma_time": "The plan must decide within 30 days for care you haven't had yet, 60 days for a bill, 7 days for a Part B drug, "
                   "or 72 hours if fast.",
        "msn": ["This is not a bill: don't pay anything from this notice. If a doctor sends a bill later, compare it with "
                "this notice, which shows the most you can be billed.",
                "Circle the items you disagree with on the notice.",
                "Fill out form CMS-20027 (Redetermination Request), or send the letter below with a copy of the notice.",
                "Mail it to the Medicare contractor address on the last page of the notice.",
                "Include any records from your doctor that help."],
        "msn_time": "The Medicare contractor usually decides within 60 days.",
        "irmaa": ["If your income went down because of a life-changing event (you retired or stopped working, your spouse died, "
                  "divorce, loss of a pension...), ask Social Security for a new decision with form SSA-44 and proof.",
                  "If you think the income they used is wrong, ask for a reconsideration with form SSA-561 (the letter below works).",
                  "Call Social Security at 1-800-772-1213 or visit your local office for help."],
        "irmaa_time": "Social Security reviews the request; you can send both a new-decision request and an appeal.",
        "anoc": ["This letter lists what changes in your plan on January 1.",
                 "I can check your plan for next year against your medicines and show the best alternative."],
        "eob": ["This is a summary of what your plan paid. It is not a bill.",
                "Check that you received each service listed. If something looks wrong, call the plan.",
                "If you also got a bill for one of these visits, send a photo of it and I'll check you're not asked to pay more."],
        "bill": ["Before you pay, check it against the statement for the same visit: the Explanation of Benefits (EOB) from "
                 "your plan, or the Medicare Summary Notice (MSN) if you have Original Medicare.",
                 "Take a photo of that statement and I'll compare them line by line."],
        "other": ["I couldn't match this to a Medicare letter I know how to act on.",
                  "Call 1-800-MEDICARE or your local SHIP for free help reading it."],
        "no_date": "I couldn't read the date on the letter. Please type the date printed at the top so I can work out the deadline.",
        "doctor_req": "Dear Dr. [name],\n\nMy Medicare plan, {plan}, denied coverage of {item}. The reason given was: \"{reason}\". "
                      "I am appealing. Could you please send the plan a supporting statement explaining why I need {item} "
                      "and why other options are not right for me? The plan's contact is on the denial notice: {plan_phone}.\n\n"
                      "Thank you,\n[Your name]\n[Your phone]",
    },
    "es": {
        "titles": {"partd_denial": "Le negaron la cobertura de una medicina", "ma_denial": "Le negaron cobertura médica",
                   "msn": "Resumen de Medicare (un resumen, no una factura)", "irmaa": "Prima más alta de la Parte B / D (IRMAA)",
                   "anoc": "Aviso Anual de Cambios (su plan el próximo año)", "nomnc": "Fin de la atención (Aviso de No Cobertura de Medicare)",
                   "eob": "Explicación de Beneficios (un resumen, no una factura)", "bill": "Una factura de un médico u hospital", "other": "Carta de Medicare"},
        "partd": ["Pida al médico que recetó la medicina que envíe al plan una declaración explicando por qué la necesita "
                  "(es obligatoria para una excepción). Puede usar la solicitud de abajo.",
                  "Envíe al plan una \"Solicitud de Redeterminación\" (sirve la carta de abajo) por correo, fax o teléfono, "
                  "con el contacto del aviso de negación.",
                  "Si esperar podría dañar seriamente su salud, pida una apelación RÁPIDA: el plan debe decidir en 72 horas.",
                  "Guarde una copia y anote la fecha en que la envió."],
        "partd_time": "El plan debe decidir en 7 días (72 horas si es rápida; 14 días si ya pagó y quiere el reembolso).",
        "ma": ["Pida a su médico una carta corta o registros que muestren por qué necesita esta atención. Puede usar la solicitud de abajo.",
               "Envíe al plan una solicitud de \"reconsideración\" (sirve la carta de abajo), con el contacto del aviso de negación.",
               "Si esperar podría dañar seriamente su salud, pida una apelación RÁPIDA: el plan debe decidir en 72 horas. "
               "Si su médico la pide, el plan debe darla.",
               "Guarde una copia y anote la fecha en que la envió."],
        "ma_time": "El plan debe decidir en 30 días si aún no recibió la atención, 60 días si es una factura, 7 días para una "
                   "medicina de la Parte B, o 72 horas si es rápida.",
        "msn": ["Esto no es una factura: no pague nada con este aviso. Si un médico le manda una factura después, compárela "
                "con este aviso, que muestra lo máximo que le pueden cobrar.",
                "Marque en el aviso los servicios con los que no está de acuerdo.",
                "Llene el formulario CMS-20027 (Solicitud de Redeterminación) o envíe la carta de abajo con una copia del aviso.",
                "Envíela a la dirección del contratista de Medicare que aparece en la última página del aviso.",
                "Incluya cualquier registro de su médico que ayude."],
        "msn_time": "El contratista de Medicare suele decidir en 60 días.",
        "irmaa": ["Si sus ingresos bajaron por un cambio de vida (se jubiló o dejó de trabajar, falleció su cónyuge, divorcio, "
                  "pérdida de una pensión...), pida al Seguro Social una nueva decisión con el formulario SSA-44 y pruebas.",
                  "Si cree que los ingresos que usaron están mal, pida una reconsideración con el formulario SSA-561 (sirve la carta de abajo).",
                  "Llame al Seguro Social al 1-800-772-1213 o visite su oficina local."],
        "irmaa_time": "El Seguro Social revisa la solicitud; puede enviar una nueva solicitud y una apelación a la vez.",
        "anoc": ["Esta carta explica qué cambia en su plan el 1 de enero.",
                 "Puedo revisar su plan del próximo año con sus medicinas y mostrarle la mejor alternativa."],
        "eob": ["Es un resumen de lo que pagó su plan. No es una factura.",
                "Revise que recibió cada servicio. Si algo parece estar mal, llame al plan.",
                "Si también recibió una factura por una de estas visitas, envíe una foto y reviso que no le cobren de más."],
        "bill": ["Antes de pagar, compárela con el resumen de la misma visita: la Explicación de Beneficios (EOB) de su plan, "
                 "o el Resumen de Medicare (MSN) si tiene Medicare Original.",
                 "Tome una foto de ese resumen y las comparo línea por línea."],
        "other": ["No pude identificar esta carta como una que sé manejar.",
                  "Llame al 1-800-MEDICARE o a su SHIP local para recibir ayuda gratis."],
        "no_date": "No pude leer la fecha de la carta. Escriba la fecha impresa arriba para calcular la fecha límite.",
        "doctor_req": "Dear Dr. [name],\n\nMy Medicare plan, {plan}, denied coverage of {item}. The reason given was: \"{reason}\". "
                      "I am appealing. Could you please send the plan a supporting statement explaining why I need {item} "
                      "and why other options are not right for me? The plan's contact is on the denial notice: {plan_phone}.\n\n"
                      "Thank you,\n[Your name]\n[Your phone]",
    },
}


def plan(kind: str, f: dict, today: date, lang: str = "en") -> dict:
    """The deterministic part of the answer: title, deadline, steps, decision time, sources."""
    t = T.get(lang, T["en"])
    notice = date.fromisoformat(f["notice_date"]) if f.get("notice_date") else None
    out = {"letter_type": kind, "title": t["titles"].get(kind, t["titles"]["other"]), "sources": SOURCES.get(kind, [])}
    days = f.get("appeal_days_stated") or 65  # what the letter prints wins; else the current rule (65)
    if kind == "partd_denial":
        out.update(deadline=_deadline(notice + timedelta(days=days) if notice else None, today, lang),
                   steps=t["partd"], decision_time=t["partd_time"])
    elif kind == "ma_denial":
        out.update(deadline=_deadline(notice + timedelta(days=days) if notice else None, today, lang),
                   steps=t["ma"], decision_time=t["ma_time"])
    elif kind == "msn":
        printed = date.fromisoformat(f["appeal_by"]) if f.get("appeal_by") else None
        out.update(deadline=_deadline(printed, today, lang), steps=t["msn"], decision_time=t["msn_time"])
    elif kind == "irmaa":
        out.update(deadline=_deadline(notice + timedelta(days=65) if notice else None, today, lang),
                   steps=t["irmaa"], decision_time=t["irmaa_time"])
    else:
        out.update(deadline=None, steps=t.get(kind, t["other"]), decision_time=None)
    if kind in ("partd_denial", "ma_denial", "msn", "irmaa") and (out.get("deadline") or {}).get("status") == "missed":
        out["late"] = LATE.get(lang, LATE["en"])
        out["steps"] = [out["late"]] + list(out["steps"])
    if kind in ("partd_denial", "ma_denial", "msn", "irmaa") and not out["deadline"]:
        out["needs_date"] = t["no_date"]
    if kind in ("partd_denial", "ma_denial"):
        out["doctor_request"] = t["doctor_req"].format(
            plan=f.get("plan_name") or "[plan name]", item=f.get("item") or "[drug or service]",
            reason=f.get("denial_reason") or "[reason on the notice]", plan_phone=f.get("plan_phone") or "[plan phone]")
    return out
