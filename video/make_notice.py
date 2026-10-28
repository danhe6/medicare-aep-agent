"""Draw a fictional, clearly marked SAMPLE care-ending notice (NOMNC layout) with a chosen end date, for the demo video.

    python video/make_notice.py 2026-10-31 2026-10-27 video/assets/nomnc_demo.jpg

The end date must be after the recording day, or the app will rightly say the appeal deadline has passed.
"""
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/Library/Fonts", "/System/Library/Fonts/Supplemental"]


def font(bold: bool, size: int):
    names = ["DejaVuSans-Bold.ttf", "Arial Bold.ttf"] if bold else ["DejaVuSans.ttf", "Arial.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def draw_notice(end: date, signed: date) -> Image.Image:
    W, H = 1100, 1420
    page = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(page)
    reg, bold, small = font(False, 19), font(True, 22), font(False, 15)
    end_txt = end.strftime("%B %-d, %Y")
    y = 60

    def line(text, f=reg, x=70, gap=27):
        nonlocal y
        d.text((x, y), text, fill="black", font=f)
        y += gap

    line("Patient name: Rosa Martinez (FICTIONAL)")
    line("Patient number: SAMPLE-000123", gap=40)
    title = "Notice of Medicare Non-Coverage"
    tw = d.textlength(title, font=font(True, 34))
    d.text(((W - tw) / 2, y), title, fill="black", font=font(True, 34))
    y += 55
    box = f"The Effective Date Coverage of Your Current Skilled Nursing Services Will End: {end_txt}"
    d.rectangle((60, y - 6, W - 60, y + 30), outline="black", width=2)
    line(box, x=72, gap=55)
    for t in ["Your Medicare provider and/or health plan have determined that Medicare probably will not pay",
              "for your current skilled nursing services after the effective date indicated above.",
              "You may have to pay for any services you receive after the above date."]:
        line(t)
    y += 18
    line("Your Right to Appeal This Decision", bold, gap=34)
    for t in ["You have the right to an immediate, independent medical review (appeal) of the decision",
              "to end Medicare coverage of these services. Your services will continue during the appeal.",
              "  • If you choose to appeal, the independent reviewer will ask for your opinion. The reviewer",
              "    also will look at your medical records and/or other relevant information. You do not",
              "    have to prepare anything in writing, but you have the right to do so if you wish.",
              "  • If you choose to appeal, you and the independent reviewer will each receive a copy of the",
              "    detailed explanation about why your coverage for services should not continue.",
              "  • If the independent reviewer decides that your services should continue, you will not be",
              "    responsible for paying for these services."]:
        line(t)
    y += 18
    line("How to Ask For an Immediate Appeal", bold, gap=34)
    for t in ["  • You must make your request to your Quality Improvement Organization (also known as a QIO).",
              "    A QIO is the independent reviewer authorized by Medicare to review the decision to end",
              "    these services.",
              "  • Your request for an immediate appeal should be made as soon as possible, but no later",
              "    than noon of the day before the effective date indicated above.",
              "  • The QIO will notify you of its decision as soon as possible, generally no later than two",
              "    days after the effective date of this notice if you are in Original Medicare. If you are in",
              "    a Medicare health plan, the QIO generally will notify you of its decision by the effective",
              "    date of this notice."]:
        line(t)
    y += 12
    d.rectangle((60, y - 6, W - 60, y + 30), outline="black", width=2)
    line("Call your QIO at: Acentra Health  1-888-317-0751  (TTY 711)  to appeal, or if you have questions.", x=72, gap=48)
    line("If You Miss The Deadline to Request An Immediate Appeal, You May Have Other Appeal Rights:", font(True, 18), gap=32)
    line("  • If you have Original Medicare: Call the QIO listed above.")
    line("  • If you belong to a Medicare health plan: Call your plan at the number given below.", gap=36)
    d.rectangle((60, y - 6, W - 60, y + 30), outline="black", width=2)
    line("Plan contact information: Sunshine Senior Advantage (FICTIONAL)  1-800-555-0199", x=72, gap=52)
    line("Additional Information: Provider: Palm Grove Rehabilitation Center (FICTIONAL), Miami, FL", gap=60)
    line("Please sign below to indicate you received and understood this notice.")
    line(f"Signature of Patient or Representative ____________________   Date: {signed.strftime('%m/%d/%Y')}")
    line("Form CMS 10123-NOMNC (layout reproduced for testing)", small)

    stamp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sf = font(True, 56)
    msg = "SAMPLE - NOT A REAL NOTICE"
    sd.text(((W - sd.textlength(msg, font=sf)) / 2, H / 2 - 30), msg, fill=(225, 80, 80, 110), font=sf)
    stamp = stamp.rotate(28, center=(W / 2, H / 2))
    page = Image.alpha_composite(page.convert("RGBA"), stamp).convert("RGB")

    # Look like a phone photo of paper on a table: dark background, slight tilt, soft shadow.
    bg = Image.new("RGB", (W + 240, H + 260), (88, 84, 80))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 140)).rotate(4, expand=True)
    bg.paste(shadow.filter(ImageFilter.GaussianBlur(14)), (130, 150), shadow.filter(ImageFilter.GaussianBlur(14)))
    tilted = page.convert("RGBA").rotate(4, expand=True, resample=Image.BICUBIC)
    bg.paste(tilted, (100, 110), tilted)
    return bg.filter(ImageFilter.GaussianBlur(0.6))


if __name__ == "__main__":
    end, signed, out = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]), Path(sys.argv[3])
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_notice(end, signed).save(out, quality=90)
    print(out)
