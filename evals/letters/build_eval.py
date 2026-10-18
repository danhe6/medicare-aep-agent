"""Build the letter-reading eval set: fictional letters, printed and "photographed", with the right answers.

Every letter is made up (invented names, plans, 555 phone numbers) and stamped SAMPLE. The wording follows the
structure of the public CMS / SSA notice templates (CMS-10146 Part D denial, CMS-10003 Medicare Advantage denial,
CMS-10123 NOMNC, the Part B Medicare Summary Notice) and the kinds of letters people ask about in online groups.
The right answers (truth.jsonl) are computed here, independently of src/letters, so the eval is not circular.

    python evals/letters/build_eval.py        # writes evals/letters/set/*.jpg + truth.jsonl (seeded, reproducible)
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "set"
R = random.Random(20261012)

FONTS = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
         ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
         ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")]
FIRST = ["Rosa", "James", "Mei", "Gloria", "Robert", "Ana", "Harold", "Linh", "Patricia", "Samuel", "Marie", "Jorge"]
LAST = ["Martinez", "Okafor", "Chen", "Johnson", "Nguyen", "Silva", "Brown", "Pierre", "Kowalski", "Haddad"]
PLANS = ["SUNSHINE SENIOR ADVANTAGE (HMO)", "GULF COAST CARE PLUS (HMO)", "BAYSIDE MEDICARE RX (PDP)",
         "EVERGREEN SENIOR CHOICE (PPO)", "HARBOR HEALTH ADVANTAGE (HMO-POS)", "PALMETTO RX SAVER (PDP)"]
DRUGS = [("Ozempic 1 mg/dose pen injector", "Ozempic", "You have not tried metformin first, as our step therapy rules require."),
         ("Eliquis 5 mg tablet", "Eliquis", "The amount requested is more than our quantity limit of 60 tablets per 30 days."),
         ("Jardiance 25 mg tablet", "Jardiance", "This drug requires prior authorization, and we did not receive the information we need."),
         ("Xarelto 20 mg tablet", "Xarelto", "This drug is not on our formulary (drug list)."),
         ("Trelegy Ellipta inhaler", "Trelegy", "This drug requires prior authorization."),
         ("Entresto 49-51 mg tablet", "Entresto", "The prescriber did not show that a lower-cost drug was tried first.")]
CARE = [("MRI of the lumbar spine", "before_care"), ("Physical therapy, 12 additional visits", "before_care"),
        ("Power wheelchair", "before_care"), ("Ambulance transport on 08/14/2026", "payment"),
        ("Skilled nursing facility stay, days 21-30", "payment"), ("Home sleep study", "before_care")]
PROVIDERS = ["Bayview Orthopedic Associates", "Lakeside Family Medicine", "Coral Gables Imaging Center", "Northside Cardiology Group"]


def fmt_date(d: date, style: int) -> str:
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    return [f"{months[d.month - 1]} {d.day}, {d.year}", f"{d.month:02d}/{d.day:02d}/{d.year}",
            f"{months[d.month - 1][:3]}. {d.day}, {d.year}", f"{d.month}/{d.day}/{d.year}"][style]


def phone() -> str:
    return f"1-{R.choice(['800', '866', '877', '888'])}-555-01{R.randint(10, 99)}"


def name() -> str:
    return f"{R.choice(FIRST)} {R.choice(LAST)}"


def partd(i):
    plan, d, style = R.choice(PLANS), date(2026, R.randint(8, 10), R.randint(1, 28)), R.randint(0, 3)
    drug, short, why = R.choice(DRUGS)
    days = R.choice([65, 65, 60, None])  # older notices print 60; some photos cut the line off
    ph = phone()
    lines = [plan, f"P.O. Box {R.randint(100, 9999)}, Tampa, FL 33601    Member Services: {ph} (TTY 711)", "",
             f"Date: {fmt_date(d, style)}", "", "Notice of Denial of Medicare Prescription Drug Coverage", "",
             f"Name: {name()}", "Member number: [REDACTED]", "",
             "We denied the prescription drug coverage that you or your prescriber requested.", f"Drug: {drug}", "",
             "Why did we deny your request?", why, "",
             "You have the right to ask us to review (appeal) our decision.", "This is called a redetermination."]
    if days:
        lines += [f"You have {days} days from the date of this notice to request a redetermination."]
    lines += ["If waiting could seriously harm your health, ask for a fast (expedited) appeal.",
              f"Call {ph} to ask for an appeal, or write to the address above."]
    truth = {"type": "partd_denial", "deadline": (d + timedelta(days=days or 65)).isoformat(), "keyword": short,
             "phone": ph[-4:]}
    return lines, truth


def ma(i):
    plan, d, style = R.choice(PLANS[:2] + PLANS[3:5]), date(2026, R.randint(8, 10), R.randint(1, 28)), R.randint(0, 3)
    item, when = R.choice(CARE)
    ph = phone()
    lines = [plan, f"Member Services: {ph}", "", "Notice of Denial of Medical Coverage", "",
             f"Date: {fmt_date(d, style)}", f"Name: {name()}", "Member number: [REDACTED]", "",
             f"Your request for {item} was denied." if when == "before_care" else f"We will not pay for: {item}.",
             "Why did we deny your request? The records we received do not show that this is medically necessary.", "",
             "You have the right to appeal our decision.",
             "You have 65 days from the date of this notice to ask for a reconsideration (appeal).",
             f"To ask for an appeal, call {ph} or write to us."]
    return lines, {"type": "ma_denial", "deadline": (d + timedelta(days=65)).isoformat(), "keyword": item.split()[0],
                   "phone": ph[-4:]}


def msn(i):
    d = date(2026, R.randint(7, 9), R.randint(1, 28))
    by = d + timedelta(days=120)
    style = R.randint(0, 3)
    prov = R.choice(PROVIDERS)
    lines = ["MEDICARE SUMMARY NOTICE", "for Part B (Medical Insurance)", "", f"{name().upper()}",
             f"THIS IS NOT A BILL      Notice date: {fmt_date(d, style)}", "",
             "Your Total You May Be Billed: $" + f"{R.randint(20, 300)}.{R.randint(0, 99):02d}", "",
             f"Claims from: {prov}", "Service: Office visit - Approved: Yes", "Service: Chest X-ray - Approved: No (see note A)", "",
             "How to handle denied claims or file an appeal",
             f"If you disagree with a decision, you must file an appeal by {fmt_date(by, style)}.",
             "Fill out the form on the last page (CMS-20027) and send it to the address listed.",
             "1-800-MEDICARE (1-800-633-4227)"]
    return lines, {"type": "msn", "deadline": by.isoformat(), "keyword": "appeal", "phone": None}


def irmaa(i):
    d = date(2026, R.randint(9, 11), R.randint(1, 28))
    style = R.randint(0, 1)
    lines = ["SOCIAL SECURITY ADMINISTRATION", "Notice of New Initial Determination - Medicare Premiums", "",
             f"Date: {fmt_date(d, style)}", f"{name()}", "",
             "We have determined that you must pay an income-related monthly adjustment amount (IRMAA)",
             "in addition to your standard Medicare Part B premium, beginning January 2027.",
             "We used your 2025 tax return information to make this decision.", "",
             "If you disagree, you may ask us to reconsider within 60 days after you receive this letter.",
             "We assume you received it 5 days after the date above.",
             "If your income went down because of a life-changing event, use form SSA-44."]
    return lines, {"type": "irmaa", "deadline": (d + timedelta(days=65)).isoformat(), "keyword": "IRMAA", "phone": None}


def nomnc(i):
    eff = date(2026, 10, R.randint(13, 28))
    qph = phone()
    style = R.randint(0, 3)
    svc = R.choice(["skilled nursing", "home health", "outpatient rehabilitation"])
    lines = [R.choice(["SUNRISE REHABILITATION CENTER", "PALM COURT NURSING & REHAB", "COASTAL HOME HEALTH SERVICES"]), "",
             "Notice of Medicare Non-Coverage", "", f"Patient name: {name()}", "Patient number: [REDACTED]", "",
             f"THE EFFECTIVE DATE COVERAGE OF YOUR CURRENT {svc.upper()} SERVICES WILL END: "
             + ("" if i == 4 else fmt_date(eff, style)), "",  # #5: the date is cut off in the photo -> must ask, not guess
             "Your Medicare provider and/or health plan have determined that Medicare probably will not pay for your",
             "current services after the effective date indicated above.", "",
             "How to ask for an immediate appeal:",
             f"Call your Quality Improvement Organization (QIO): Acentra Health at {qph}",
             "You must make your request no later than noon of the day before the effective date indicated above."]
    code = {"skilled nursing": "snf", "home health": "home_health", "outpatient rehabilitation": "corf"}[svc]
    return lines, {"type": "nomnc", "effective_date": None if i == 4 else eff.isoformat(), "keyword": code, "phone": qph[-4:]}


def anoc(i):
    plan = R.choice(PLANS)
    pid = f"H{R.randint(1000, 9999)}-{R.randint(1, 99):03d}"
    lines = [plan, f"Plan ID {pid}", "", "Annual Notice of Change for 2027", "",
             "You are currently enrolled as a member of our plan. Next year, there will be changes to the plan's",
             "costs and benefits. Please see page 4 for a summary of important costs, including premium.",
             "What to do now: 1. ASK which changes apply to you. 2. COMPARE: learn about other plan choices.",
             "3. CHOOSE: decide whether you want to change your plan by December 7."]
    return lines, {"type": "anoc", "keyword": pid, "phone": None}


def eob(i):
    plan = R.choice(PLANS[:2] + PLANS[3:5])
    lines = [plan, "Explanation of Benefits", "THIS IS NOT A BILL", "", f"Member: {name()}",
             "Claims processed August 1 - August 31, 2026", "",
             f"Provider: {R.choice(PROVIDERS)}   Date of service: 08/12/2026",
             "Office visit   Billed $210.00   Plan paid $170.00   You owe $40.00",
             "Total you owe the provider: $40.00"]
    return lines, {"type": "eob", "keyword": "Explanation", "phone": None}


def bill(i):
    prov = R.choice(PROVIDERS)
    lines = [prov.upper(), "PATIENT STATEMENT", "", f"Statement date: {fmt_date(date(2026, 10, R.randint(1, 9)), 1)}",
             f"Patient: {name()}   Account: [REDACTED]", "",
             "08/12/2026  Office visit, established patient    $40.00",
             "08/12/2026  X-ray, knee, 3 views                  $75.00", "",
             "AMOUNT DUE: $115.00     Please pay by 11/01/2026"]
    return lines, {"type": "bill", "keyword": "115", "phone": None}


def not_medicare(i):
    kinds = [["FRESH MARKET #214", "Bananas 1.29", "Whole milk 3.49", "Bread 2.99", "TOTAL 7.77", "THANK YOU FOR SHOPPING"],
             ["CITY ELECTRIC & WATER", "Account summary", "Electric service 09/01-09/30   $86.12", "Water   $31.40",
              "Amount due by 10/25/2026: $117.52"],
             ["LUNCH MENU", "Soup of the day   6", "Turkey club   11", "Garden salad   9", "Iced tea   3"],
             ["Dentist Tues 10am", "call Maria"]]
    return kinds[i % len(kinds)], {"type": "not_medicare", "phone": None}


def nonrenewal(i):
    plan = R.choice(PLANS)
    pid = f"H{R.randint(1000, 9999)}-{R.randint(1, 99):03d}" if "PDP" not in plan else f"S{R.randint(1000, 9999)}-{R.randint(1, 99):03d}"
    d = date(2026, 10, R.randint(1, 5))
    opener = ["Important: Your plan will not be offered in 2027.",
              "Your Medicare plan is leaving the Medicare program.",
              f"{plan.title()} has decided not to renew its contract with Medicare for 2027.",
              "This is a Plan Non-Renewal Notice.",
              "Your plan won't be available next year."][i % 5]
    lines = [plan, f"Plan ID {pid}", "", f"{fmt_date(d, R.randint(0, 3))}", f"Dear {name()},", "", opener, "",
             "Your current coverage will continue through December 31, 2026.",
             "You must choose new coverage. You can join another plan during Open Enrollment, October 15 - December 7.",
             "Because your plan is ending, you also have a Special Enrollment Period through the end of February 2027.",
             "If you do not choose a plan, you will be enrolled in Original Medicare on January 1, 2027.",
             f"Questions? Call Member Services at {phone()}."]
    return lines, {"type": "nonrenewal", "deadline": "2026-12-31", "keyword": pid, "phone": None}


MAKERS = [(partd, 8), (ma, 6), (msn, 5), (irmaa, 4), (nomnc, 5), (anoc, 3), (eob, 3), (bill, 3), (not_medicare, 4), (nonrenewal, 5)]


def render(lines: list[str], style: str) -> Image.Image:
    reg, bold = R.choice(FONTS)
    f, fb = ImageFont.truetype(reg, 22), ImageFont.truetype(bold, 26)
    W, H = 1275, max(1100, 140 + 36 * len(lines))
    page = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(page)
    import textwrap
    wrapped = []
    for line in lines:  # real letters wrap long lines; a line running off the page would hide its date
        wrapped += textwrap.wrap(line, 72) or [""]
    lines = wrapped
    H = max(1100, 140 + 36 * len(lines))
    page = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(page)
    for i, line in enumerate(lines + ["", "SAMPLE FOR TESTING - NOT A REAL NOTICE"]):
        d.text((70, 70 + 36 * i), line, fill=(25, 25, 25), font=fb if i == 0 or line.isupper() and len(line) > 12 else f)
    if style == "scan":
        return page
    # a phone photo of the printed page: on a desk, a little rotated, uneven light, a bit soft
    desk = Image.new("RGB", (W + 240, H + 240), R.choice([(120, 96, 70), (90, 90, 95), (180, 170, 150)]))
    desk.paste(page.rotate(R.uniform(-3.5, 3.5), expand=False, fillcolor=(235, 235, 230)), (120, 120))
    shade = Image.linear_gradient("L").resize(desk.size).rotate(R.choice([0, 90, 180, 270]))
    dark = 0.55 if style == "dark" else 0.82
    desk = Image.composite(desk, Image.eval(desk, lambda v: int(v * dark)), shade)
    return desk.filter(ImageFilter.GaussianBlur(R.uniform(0.4, 1.1)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for maker, n in MAKERS:
        for i in range(n):
            lines, truth = maker(i)
            style = R.choice(["scan", "photo", "photo", "dark"])
            sid = f"{truth['type']}_{i + 1:02d}"
            render(lines, style).save(OUT / f"{sid}.jpg", "JPEG", quality=R.choice([70, 85]))
            rows.append({"id": sid, "file": f"set/{sid}.jpg", "style": style, **truth})
    (HERE / "truth.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"{len(rows)} letters -> {OUT}")


if __name__ == "__main__":
    main()
