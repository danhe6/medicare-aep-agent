"""Record the demo video's screen footage from the LIVE site with Playwright. Nothing is faked: every answer on screen
comes from the deployed app at recording time. Each scene is one .webm plus a marks.json of when the app was busy
(waiting on the model), so build.py can speed up only those parts and label them "sped up".

    pip install playwright && python -m playwright install chromium
    python video/record.py https://89-124-36-137.sslip.io video/out
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
LABEL = HERE.parent / "evals" / "fixtures" / "rx_label_sample.png"
NOTICE = HERE / "assets" / "nomnc_demo.jpg"
DESKTOP = {"width": 1280, "height": 720}
PHONE = {"width": 390, "height": 844}
LONG = 150_000  # ms: the model can be slow; never cut a real answer short


class Scene:
    """One recorded clip with time marks (seconds from the start of the clip)."""

    def __init__(self, browser, out: Path, name: str, viewport: dict, scale: int = 1):
        self.name, self.out = name, out
        size = {"width": viewport["width"] * scale, "height": viewport["height"] * scale}
        self.ctx = browser.new_context(viewport=viewport, device_scale_factor=scale, locale="en-US",
                                       record_video_dir=str(out / name), record_video_size=size,
                                       is_mobile=scale > 1, has_touch=scale > 1)
        self.page = self.ctx.new_page()
        self.t0 = time.monotonic()
        self.marks: list[dict] = []

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 2)

    def busy(self, fn, label: str):
        """Run fn (which waits for the app) and mark that span as waiting time."""
        start = self.now()
        fn()
        self.marks.append({"kind": "wait", "label": label, "start": start, "end": self.now()})

    def start(self):
        """Footage before this (blank page, loading, clearing storage) is cut in editing."""
        self.marks.append({"kind": "start", "start": self.now()})

    def pause(self, s: float):
        self.page.wait_for_timeout(int(s * 1000))

    def close(self):
        self.marks.append({"kind": "end", "start": self.now()})
        video = self.page.video
        self.ctx.close()
        path = Path(video.path())
        final = self.out / f"{self.name}.webm"
        path.replace(final)
        (self.out / f"{self.name}.json").write_text(json.dumps(self.marks, indent=1))
        print(f"{self.name}: {self.marks[-1]['start']:.0f}s -> {final}")


SEND = "() => { const b = document.querySelector('form button[type=submit]'); return b && %s b.disabled; }"


def answer_done(page):
    """Wait for one full assistant turn: the send button goes disabled while it works and comes back when it's done.
    (Waiting on the button, not on the model's wording, so a rephrased answer can't stall the recording.)"""
    try:
        page.wait_for_function(SEND % "", timeout=20_000)
    except Exception:
        pass  # the turn may have started and ended before we looked
    page.wait_for_function(SEND % "!", timeout=LONG)
    page.wait_for_timeout(800)


def type_slowly(page, text: str):
    box = page.get_by_placeholder("Type here…")
    box.click()
    box.press_sequentially(text, delay=35)
    box.press("Enter")


def scroll_to_text(page, text: str, pause_ms: int = 1500):
    page.get_by_text(text).first.scroll_into_view_if_needed()
    page.wait_for_timeout(pause_ms)


def opening(browser, out, base):
    s = Scene(browser, out, "s0_opening", DESKTOP)
    p = s.page
    p.goto(base + "/", wait_until="networkidle")
    s.start()
    s.pause(3)
    p.get_by_text("THE PROBLEM", exact=False).first.scroll_into_view_if_needed()
    s.pause(1)
    p.mouse.wheel(0, 250)
    s.pause(6)
    s.close()


def family_flow(browser, out, base):
    """Steps 1-3 in one session: label photo -> comparison -> doctor check -> Spanish family summary."""
    s = Scene(browser, out, "s1_to_s3_family", DESKTOP)
    p = s.page
    p.goto(base + "/app", wait_until="networkidle")
    p.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    p.reload(wait_until="networkidle")
    s.start()
    s.pause(1.5)
    p.get_by_text("Someone I help").click()
    s.pause(1.5)
    p.get_by_text("Help me pick a plan").click()
    s.pause(1.5)
    s.marks.append({"kind": "cut", "label": "step1", "start": s.now()})
    with p.expect_file_chooser() as fc:
        p.get_by_text("Or take a photo of the pill bottles").click()
    fc.value.set_files(str(LABEL))
    s.busy(lambda: answer_done(p), "reading the label")
    s.pause(3)

    s.marks.append({"kind": "cut", "label": "step2", "start": s.now()})
    type_slowly(p, "Mom lives in Miami-Dade, Florida. She also takes Eliquis 5 mg twice a day. No Medicaid.")
    s.busy(lambda: answer_done(p), "comparing every plan")
    scroll_to_text(p, "Best plans for these medicines", 2500)
    p.mouse.wheel(0, 300)
    s.pause(3)
    scroll_to_text(p, "needs plan approval", 3000)
    p.mouse.wheel(0, 500)
    s.pause(3)

    s.marks.append({"kind": "cut", "label": "step3", "start": s.now()})
    p.get_by_role("button", name="Is their doctor in network?").click()
    s.busy(lambda: answer_done(p), "asking which doctor")
    s.pause(1)
    type_slowly(p, "Dr. Maria Lopez, the general practice PA in Miami Beach")
    s.busy(lambda: answer_done(p), "searching plan directories")
    s.pause(1)
    scroll_to_text(p, "Online directories are often out of date", 3500)
    p.get_by_role("button", name="Send a summary to family").last.click()
    s.pause(1)
    p.get_by_label("Language").select_option("es")
    s.pause(1)
    p.get_by_role("button", name="Write it").click()
    s.busy(lambda: p.get_by_text("Numbers checked against the results above").wait_for(timeout=LONG),
           "writing the family summary")
    scroll_to_text(p, "Numbers checked against the results above", 5000)
    s.close()


def senior_spanish(browser, out, base):
    """Step 4 at phone size: big-text mode in Spanish, photo of a care-ending notice -> appeal card."""
    s = Scene(browser, out, "s4_senior_es", PHONE, scale=2)
    p = s.page
    p.goto(base + "/app", wait_until="networkidle")
    p.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    p.reload(wait_until="networkidle")
    s.start()
    s.pause(1)
    p.get_by_role("button", name="Español").click()
    s.pause(1.5)
    p.get_by_text("A mí", exact=True).first.click()
    s.pause(2)
    with p.expect_file_chooser() as fc:
        p.get_by_text("¿Recibió una carta o una factura?").click()
    fc.value.set_files(str(NOTICE))
    s.busy(lambda: answer_done(p), "leyendo el aviso")
    p.evaluate("() => window.scrollTo(0, 0)")
    s.pause(1)
    for _ in range(6):
        p.mouse.wheel(0, 420)
        s.pause(1.6)
    s.close()


def closing(browser, out, base):
    s = Scene(browser, out, "s5_close", DESKTOP)
    s.page.goto(base + "/", wait_until="networkidle")
    s.start()
    s.pause(8)
    s.close()


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else HERE / "out")
    out.mkdir(parents=True, exist_ok=True)
    for f in (LABEL, NOTICE):
        assert f.exists(), f"missing {f} (run video/make_notice.py first)"
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, fn in [("s0", opening), ("s1", family_flow), ("s4", senior_spanish), ("s5", closing)]:
            if only and name not in only:
                continue
            fn(browser, out, base)
        browser.close()
