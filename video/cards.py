"""Still cards for the demo video (hook stats, architecture, evals, title), drawn with Pillow at 1280x720.
Each card is a list of stages; a stage adds one more element, so build.py can reveal them one by one.
Every figure here must match a source: KFF numbers are the ones cited on the site's home page; accuracy and eval
numbers are from evals/ (440-case Plan Finder comparison, 150-run agent eval)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG, INK, MUTED, BRAND, GOLD, CARD, LINE = "#F7F8F4", "#1F2A24", "#5D6B63", "#2F5D50", "#B8862B", "#FFFFFF", "#DCE3DD"
SERIF = ["/System/Library/Fonts/Supplemental/Georgia Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
SANS_B = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _f(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def _canvas():
    im = Image.new("RGB", (W, H), BG)
    return im, ImageDraw.Draw(im)


def _wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def _text(d, xy, text, font, fill, width=None, gap=8):
    x, y = xy
    for line in (_wrap(d, text, font, width) if width else [text]):
        d.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def hook() -> list[Image.Image]:
    """Three sourced numbers, revealed one at a time."""
    rows = [("32", "Medicare Advantage drug plans to choose from, on average", "KFF, Oct 2025 (2026 plans)"),
            ("69%", "of people with Medicare didn't compare their options at open enrollment", "KFF, 2022 coverage year"),
            ("81%", "of appealed prior-authorization denials were overturned, yet only 11.5% were appealed", "KFF, 2024 data")]
    out = []
    for n in range(1, len(rows) + 1):
        im, d = _canvas()
        d.text((90, 70), "EVERY FALL", font=_f(SANS_B, 22), fill=BRAND)
        y = 130
        for big, line, src in rows[:n]:
            d.text((90, y), big, font=_f(SERIF, 96), fill=INK)
            yy = _text(d, (380, y + 14), line, _f(SANS, 30), INK, width=780)
            d.text((380, yy + 2), src, font=_f(SANS, 18), fill=MUTED)
            y += 180
        out.append(im)
    return out


def title() -> list[Image.Image]:
    im, d = _canvas()
    d.text((90, 250), "Medicare Helper", font=_f(SERIF, 84), fill=INK)
    d.text((94, 360), "Neutral help choosing and defending Medicare coverage", font=_f(SANS, 32), fill=MUTED)
    d.text((94, 420), "For people with Medicare and the families who help them · English and Español",
           font=_f(SANS, 24), fill=BRAND)
    return [im]


def _box(d, xy, text, sub=None, fill=CARD, outline=LINE, color=INK, w=250, h=78):
    x, y = xy
    d.rounded_rectangle((x, y, x + w, y + h), radius=16, fill=fill, outline=outline, width=2)
    d.text((x + 16, y + 12), text, font=_f(SANS_B, 20), fill=color)
    if sub:
        d.text((x + 16, y + 42), sub, font=_f(SANS, 16), fill=MUTED if color == INK else color)


def _arrow(d, a, b, color=MUTED):
    d.line((a, b), fill=color, width=3)
    (x1, y1), (x2, y2) = a, b
    if abs(x2 - x1) >= abs(y2 - y1):
        s = 1 if x2 > x1 else -1
        d.polygon([(x2, y2), (x2 - 12 * s, y2 - 7), (x2 - 12 * s, y2 + 7)], fill=color)
    else:
        s = 1 if y2 > y1 else -1
        d.polygon([(x2, y2), (x2 - 7, y2 - 12 * s), (x2 + 7, y2 - 12 * s)], fill=color)


def architecture() -> list[Image.Image]:
    """Two stages: the model and its tools, then the code check that every number passes before it's shown."""
    def base():
        im, d = _canvas()
        d.text((60, 40), "UNDER THE HOOD", font=_f(SANS_B, 22), fill=BRAND)
        d.text((60, 74), "The model talks. Code computes every number.", font=_f(SERIF, 40), fill=INK)
        _box(d, (60, 300), "Photo or question", "pill bottle, notice, bill", w=230)
        _box(d, (350, 280), "Nemotron agent", "Nebius Token Factory", fill=BRAND, outline=BRAND, color="#FFFFFF", w=250, h=118)
        d.text((366, 352), "3 Super · 3.5 Super VL", font=_f(SANS, 16), fill="#DCE6E1")
        _arrow(d, (290, 339), (348, 339))
        tools = [("compare_plans", "Medicare plan files + cost engine"), ("find_drug", "NLM RxNorm"),
                 ("check_doctor", "CMS NPPES + Tavily search"), ("read_letter", "vision + coded deadline rules"),
                 ("family_summary", "Nemotron 3 Ultra, re-checked")]
        for i, (t, s) in enumerate(tools):
            y = 150 + i * 92
            _box(d, (680, y), t, s, w=300, h=74)
            _arrow(d, (600, 339), (678, y + 37))
        return im, d
    im1, _ = base()
    im2, d2 = base()
    d2.rounded_rectangle((1010, 250, 1240, 430), radius=18, fill="#FFF7E6", outline=GOLD, width=3)
    d2.text((1028, 266), "Checked by code", font=_f(SANS_B, 21), fill=INK)
    _text(d2, (1028, 302), "Every $, %, star rating and dose in a reply must come from a tool. If not, it is rewritten.",
          _f(SANS, 16), INK, width=196, gap=6)
    _arrow(d2, (980, 339), (1008, 339), GOLD)
    return [im1, im2]


def evals() -> list[Image.Image]:
    """The eval story, then the numbers."""
    def story(d):
        d.text((90, 60), "WE TEST IT LIKE WE DON'T TRUST IT", font=_f(SANS_B, 22), fill=BRAND)
        d.text((90, 96), "Evals that lied, and the checks that fixed them", font=_f(SERIF, 40), fill=INK)
        items = ["A tool crashed, and the eval still said PASS",
                 "An injectable pen was priced as a pill, and the eval still said PASS",
                 "Now the evals check the tool output and the exact product priced"]
        y = 180
        for i, t in enumerate(items):
            if i < 2:
                d.text((98, y - 2), "\u00d7", font=_f(SANS_B, 34), fill="#B4442E")
            else:
                d.line([(97, y + 17), (107, y + 27), (124, y + 6)], fill=BRAND, width=4)
            d.text((140, y + 2), t, font=_f(SANS, 26), fill=INK)
            y += 52
    im1, d1 = _canvas()
    story(d1)
    im2, d2 = _canvas()
    story(d2)
    stats = [("98.2%", "of 440 cases within 10% or $100 a year of Medicare's Plan Finder"),
             ("0", "coverage disagreements with Plan Finder"),
             ("150/150", "agent test conversations passed")]
    for i, (big, line) in enumerate(stats):
        x = 90 + i * 380
        d2.rounded_rectangle((x, 400, x + 350, 640), radius=20, fill=CARD, outline=LINE, width=2)
        d2.text((x + 24, 420), big, font=_f(SERIF, 64), fill=BRAND)
        _text(d2, (x + 24, 510), line, _f(SANS, 22), INK, width=300, gap=6)
    return [im1, im2]


def closing() -> list[Image.Image]:
    im, d = _canvas()
    d.text((90, 230), "Medicare Helper", font=_f(SERIF, 72), fill=INK)
    d.text((94, 330), "Neutral help, in English and Español.", font=_f(SANS, 34), fill=INK)
    d.text((94, 400), "89-124-36-137.sslip.io", font=_f(SANS_B, 30), fill=BRAND)
    d.text((94, 470), "Rosa is fictional. The plan data is real: Medicare's public plan files.", font=_f(SANS, 22), fill=MUTED)
    d.text((94, 505), "Built with NVIDIA Nemotron on Nebius Token Factory, and Tavily.", font=_f(SANS, 22), fill=MUTED)
    return [im]


CARDS = {"hook": hook, "title": title, "architecture": architecture, "evals": evals, "closing": closing}


def render(name: str, out_dir: Path) -> list[Path]:
    paths = []
    for i, im in enumerate(CARDS[name]()):
        p = out_dir / f"card_{name}_{i}.png"
        im.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "video/out/cards")
    out.mkdir(parents=True, exist_ok=True)
    for n in CARDS:
        print(*render(n, out), sep="\n")
