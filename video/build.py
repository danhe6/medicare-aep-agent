"""Edit the recorded clips into the demo video: macOS `say` voiceover + ffmpeg. Only the spans where the app was waiting
on the model are sped up, and those carry an on-screen "sped up" label. Writes demo.mp4 and demo.srt (captions).

    python video/build.py video/out
    python video/build.py video/out --voice "Ava (Premium)"
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
W, H, FPS = 1280, 720, 30
BG = "0xF7F8F4"
INK = "0x1F2A24"
BRAND = "0x2F5D50"
FONTS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
MAX_TOTAL = 175.0  # the rules say under 3 minutes; leave a margin


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"command failed: {' '.join(cmd[:6])} ...\n{r.stderr[-1500:]}")
    return r.stdout


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())


def font() -> str:
    for f in FONTS:
        if Path(f).exists():
            return f
    raise SystemExit("no bold font found; edit FONTS in build.py")


def text_file(tmp: Path, name: str, text: str) -> str:
    p = tmp / f"{name}.txt"
    p.write_text(text)
    return str(p).replace(":", "\\:")


def voiceover(tmp: Path, sid: str, text: str, voice: str, rate: int) -> tuple[Path, float]:
    aiff, wav = tmp / f"{sid}.aiff", tmp / f"{sid}.wav"
    if not shutil.which("say"):  # not a Mac: silent stand-in of about the right length, for testing the edit only
        secs = len(text.split()) / rate * 60
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{secs:.2f}", str(wav)])
        return wav, duration(wav)
    run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(aiff), "-ar", "48000", "-ac", "2", str(wav)])
    return wav, duration(wav)


def segments(marks: list[dict], start: float, end: float) -> list[tuple[float, float, bool]]:
    """Split [start, end] into (a, b, is_wait) pieces using the recorded wait spans."""
    out, t = [], start
    for m in sorted((m for m in marks if m["kind"] == "wait"), key=lambda m: m["start"]):
        a, b = max(m["start"], start), min(m["end"], end)
        if b <= a:
            continue
        if a > t:
            out.append((t, a, False))
        out.append((a, b, True))
        t = b
    if end > t:
        out.append((t, end, False))
    return [s for s in out if s[1] - s[0] > 0.05]


def mark_time(marks: list[dict], name: str) -> float:
    if name == "start":
        return next((m["start"] for m in marks if m["kind"] == "start"), 0.0)
    if name == "end":
        return next(m["start"] for m in marks if m["kind"] == "end")
    return next(m["start"] for m in marks if m["kind"] == "cut" and m["label"] == name)


def render_scene(tmp: Path, sid: str, clip: Path, pieces, wait_speed: float, title: str, min_len: float, fnt: str,
                 phone: bool) -> Path:
    """One scene: each piece trimmed and (if waiting) sped up and labelled, then the title banner over the whole scene."""
    parts = []
    for i, (a, b, wait) in enumerate(pieces):
        speed = wait_speed if wait else 1.0
        vf = [f"trim=start={a:.2f}:end={b:.2f}", f"setpts=(PTS-STARTPTS)/{speed:.3f}", f"fps={FPS}"]
        if phone:
            vf += [f"scale=-2:{H}", f"pad={W}:{H}:(ow-iw)/2:0:color={BG}"]
        else:
            vf += [f"scale={W}:{H}"]
        if wait:
            label = text_file(tmp, f"{sid}_{i}_w", f"sped up {speed:.0f}x (real wait for the model)")
            vf.append(f"drawtext=fontfile='{fnt}':textfile='{label}':fontsize=22:fontcolor=white:box=1:boxcolor=0x000000@0.55:"
                      f"boxborderw=10:x=w-tw-24:y=h-th-24")
        part = tmp / f"{sid}_{i}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-vf", ",".join(vf), "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-r", str(FPS), str(part)])
        parts.append(part)
    lst = tmp / f"{sid}_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    joined = tmp / f"{sid}_joined.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    vf = []
    pad = max(0.0, min_len - duration(joined))
    if pad > 0:
        vf.append(f"tpad=stop_mode=clone:stop_duration={pad:.2f}")
    if title:
        tf = text_file(tmp, f"{sid}_title", title)
        vf.append(f"drawtext=fontfile='{fnt}':textfile='{tf}':fontsize=30:fontcolor=white:box=1:boxcolor={BRAND}@0.92:"
                  f"boxborderw=14:x=28:y=24")
    out = tmp / f"{sid}.mp4"
    if vf:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(joined), "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])
    else:
        shutil.copy(joined, out)
    return out


def end_card(tmp: Path, lines: list[str], fnt: str, secs: float = 4.0) -> Path:
    out = tmp / "end.mp4"
    draws = []
    for i, line in enumerate(lines):
        tf = text_file(tmp, f"end{i}", line)
        size = 38 if i == 0 else 26
        color = INK if i == 0 else BRAND
        draws.append(f"drawtext=fontfile='{fnt}':textfile='{tf}':fontsize={size}:fontcolor={color}:x=(w-tw)/2:y=h/2-60+{i * 70}")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:d={secs}:r={FPS}", "-vf", ",".join(draws),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])
    return out


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def captions(cues: list[tuple[float, float, str]]) -> str:
    """One caption per sentence, timed in proportion to its length within the scene's voiceover."""
    out, n = [], 1
    for start, dur, text in cues:
        sentences = [s.strip() + "." for s in text.replace("?", "?.").split(".") if s.strip()]
        sentences = [s.replace("?.", "?") for s in sentences]
        total = sum(len(s) for s in sentences) or 1
        t = start
        for s in sentences:
            d = dur * len(s) / total
            out.append(f"{n}\n{srt_time(t)} --> {srt_time(t + d)}\n{s}\n")
            n, t = n + 1, t + d
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", type=Path)
    ap.add_argument("--voice")
    ap.add_argument("--rate", type=int)
    ap.add_argument("--out", type=Path, default=HERE / "demo.mp4")
    a = ap.parse_args()
    cfg = json.loads((HERE / "narration.json").read_text())
    voice, rate = a.voice or cfg["voice"], a.rate or cfg["rate"]
    fnt = font()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        scenes, cues, audio, t = [], [], [], 0.0
        for sc in cfg["scenes"]:
            clip = a.clips / f"{sc['clip']}.webm"
            marks = json.loads((a.clips / f"{sc['clip']}.json").read_text())
            start, end = mark_time(marks, sc.get("from", "start")), mark_time(marks, sc.get("to", "end"))
            pieces = segments(marks, start, end)
            wav, vo = voiceover(tmp, sc["id"], sc["text"], voice, rate)
            target = vo + 1.2
            normal = sum(b - a for a, b, w in pieces if not w)
            waiting = sum(b - a for a, b, w in pieces if w)
            room = max(target - normal, 2.0)
            speed = min(max(waiting / room, 2.0), 24.0) if waiting else 1.0
            path = render_scene(tmp, sc["id"], clip, pieces, speed, sc.get("title", ""), target, fnt, "s4" in sc["id"])
            d = duration(path)
            print(f"{sc['id']}: voice {vo:5.1f}s  footage {normal:5.1f}s + waits {waiting:5.1f}s at {speed:.0f}x  -> {d:5.1f}s")
            scenes.append(path)
            cues.append((t + 0.3, vo, sc["text"]))
            audio.append((wav, d))
            t += d
        scenes.append(end_card(tmp, cfg["end_card"], fnt))
        t += 4.0
        lst = tmp / "all.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in scenes))
        video = tmp / "video.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)])
        # Voiceover: each scene's audio starts 0.3 s into its scene; silence fills the rest.
        inputs, filters, offset = [], [], 0.0
        for i, (wav, d) in enumerate(audio):
            inputs += ["-i", str(wav)]
            ms = int((offset + 0.3) * 1000)
            filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
            offset += d
        mix = "".join(f"[a{i}]" for i in range(len(audio))) + f"amix=inputs={len(audio)}:normalize=0,apad,atrim=0:{t:.2f}[vo]"
        voice_track = tmp / "voice.m4a"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters + [mix]), "-map", "[vo]",
             "-c:a", "aac", "-b:a", "160k", str(voice_track)])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(voice_track), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(a.out)])
    a.out.with_suffix(".srt").write_text(captions(cues))
    total = duration(a.out)
    print(f"\n{a.out}  {total:.1f}s" + ("" if total <= MAX_TOTAL else f"  <-- OVER {MAX_TOTAL:.0f}s: shorten a scene's text"))
    print(f"{a.out.with_suffix('.srt')}  (upload to YouTube as captions)")


if __name__ == "__main__":
    main()
