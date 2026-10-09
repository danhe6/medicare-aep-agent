"""Make SAMPLE Medicare letters (fictional people, plans and 555 phone numbers) as text + PNG, for tests and demos.
Wording follows the structure of the public CMS / SSA notice templates; nothing here is a real person's letter.

    python evals/fixtures/letters/make_samples.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SAMPLES = {
"partd_denial": """SUNSHINE SENIOR ADVANTAGE (HMO)
P.O. Box 1234, Tampa, FL 33601        Member Services: 1-800-555-0199

Date: October 2, 2026

Notice of Denial of Medicare Prescription Drug Coverage

Member name: Rosa Martinez
Member ID: [REDACTED]

We denied the prescription drug coverage that you or your prescriber requested.
Drug: Ozempic 1 mg/dose pen injector

Why did we deny your request?
This drug requires prior authorization. The information we received does not show
that you have tried metformin first, as required by our plan's step therapy rules.

You have the right to request a redetermination (appeal) of our decision.
You have 65 days from the date of this notice to request an appeal.
If you think waiting 7 days could seriously harm your health, ask for a fast appeal.

SAMPLE LETTER FOR TESTING - NOT A REAL NOTICE""",

"ma_denial": """GULF COAST CARE PLUS (HMO)
Member Services: 1-866-555-0142

Notice of Denial of Medical Coverage

Date: September 30, 2026
Name: Walter Chen

We have denied the medical services/items listed below that you or your physician requested:
Outpatient physical therapy, 12 visits (knee)

Why did we deny your request?
The records we received do not show that the services are medically necessary.
Only 6 visits were approved under our coverage guidelines.

You have the right to appeal our decision. You must ask for a reconsideration within
65 days of the date of this notice. If waiting 30 days could seriously harm your
health, you or your doctor can ask for a fast (expedited) reconsideration.

SAMPLE LETTER FOR TESTING - NOT A REAL NOTICE""",

"irmaa": """SOCIAL SECURITY ADMINISTRATION
Notice of New Initial Determination - Income-Related Monthly Adjustment Amount

Date: September 22, 2026
To: Linda Okafor

We are writing to tell you that you must pay an income-related monthly adjustment
amount (IRMAA) for your Medicare Part B and prescription drug coverage in 2027.
We used information from your 2025 federal tax return provided by the IRS.

If you disagree, you can ask for a reconsideration within 60 days of receiving this
letter. If your income has gone down because of a life-changing event, you can ask
us to use more recent information.

SAMPLE LETTER FOR TESTING - NOT A REAL NOTICE""",

"msn": """MEDICARE SUMMARY NOTICE for Part B (Medical Insurance)
The Official Summary of Your Medicare Claims from the Centers for Medicare & Medicaid Services

Notice date: September 15, 2026
Name: George Alvarez

Did Medicare approve all services or claims? NO
If you disagree with a decision, you must file an appeal by January 14, 2027.

Services denied:
  Ambulance transport, 08/20/2026 - Medicare does not pay for this service because it was not medically necessary.
  Wheelchair rental, 08/25/2026 - Not covered without a doctor's order on file.

To appeal, fill out the Redetermination Request Form (CMS-20027) and send it to the
Medicare contractor at the address on the last page.

SAMPLE LETTER FOR TESTING - NOT A REAL NOTICE""",

"bill": """BAYVIEW ORTHOPEDIC ASSOCIATES
450 Harbor Blvd, Tampa, FL 33602        Billing office: 1-813-555-0177

PATIENT STATEMENT                    Statement date: 10/01/2026
Patient: Walter Chen                 Account: [REDACTED]

Date of service   Description                         Charges   Insurance paid   Amount due
08/12/2026        Office visit, established patient   $210.00   $170.00          $40.00
08/12/2026        X-ray, knee, 3 views                $145.00   $70.00           $75.00

AMOUNT DUE: $115.00        Please pay this amount by 10/31/2026

SAMPLE BILL FOR TESTING - NOT A REAL BILL""",

"eob": """GULF COAST CARE PLUS (HMO)
Explanation of Benefits - THIS IS NOT A BILL

Member: Walter Chen                  Claims processed September 2026

Date of service   Provider                         Service                      Plan paid   Your share
08/12/2026        Bayview Orthopedic Associates    Specialist office visit      $170.00     $40.00
08/12/2026        Bayview Orthopedic Associates    Diagnostic X-ray, knee       $70.00      $15.00

Your share is the most an in-network provider can bill you for these services.

SAMPLE STATEMENT FOR TESTING - NOT A REAL EOB""",
}


def render(text: str, out: Path) -> None:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 20)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    lines = text.splitlines()
    img = Image.new("RGB", (1280, 120 + 34 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        f = bold if i == 0 or line.startswith(("Notice of", "MEDICARE SUMMARY", "SOCIAL SECURITY", "Explanation of", "PATIENT STATEMENT")) else font
        d.text((60, 60 + 34 * i), line, fill="black", font=f)
    img.save(out)


if __name__ == "__main__":
    for name, text in SAMPLES.items():
        (HERE / f"{name}.txt").write_text(text)
        render(text, HERE / f"{name}.png")
        print("wrote", name)
