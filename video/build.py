"""Edit the recorded clips and the still cards into the demo video.

Real footage only: the app parts come from video/record.py run against the live site. Spans where the app was waiting
on the model are sped up and labelled "sped up". Where record.py marked a focus (the comparison table, the appeal
card), the shot dissolves to a still close-up and back, so nothing moves while the eye reads. Voiceover: Kokoro
(open-source TTS, runs locally), or macOS `say`. Captions are burned in and also written to demo.srt.

    python video/build.py video/out
    python video/build.py video/out --voice am_michael --music video/assets/music.mp3
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cards

HERE = Path(__file__).parent
W, H, FPS = 1280, 720, 30
W2, H2 = 2 * W, 2 * H  # working frame: clips are recorded at 2x so close-ups stay sharp
BG, BRAND = "0xF7F8F4", "0x2F5D50"
FONTS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
MAX_TOTAL = 178.0  # the rules say under 3 minutes
XF = 0.4           # dissolve length, seconds
VENC: list[str] = []
_KOKORO = []


def run(cmd: list) -> str:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"command failed: {' '.join(map(str, cmd[:8]))} ...\n{r.stderr[-1500:]}")
    return r.stdout


def pick_encoder() -> list[str]:
    """libx264 if this ffmpeg has it, else the Mac hardware encoder, else OpenH264 (conda-forge builds often lack x264)."""
    encs = run(["ffmpeg", "-hide_banner", "-encoders"])
    if " libx264 " in encs:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    if " h264_videotoolbox " in encs:
        return ["-c:v", "h264_videotoolbox", "-b:v", "8M"]
    if " libopenh264 " in encs:
        return ["-c:v", "libopenh264", "-b:v", "8M"]
    raise SystemExit("this ffmpeg has no H.264 encoder; try: brew install ffmpeg")


def encode(args: list, out: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", *args, *VENC, "-pix_fmt", "yuv420p", "-r", FPS, out])
    return out


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def font() -> str:
    for f in FONTS:
        if Path(f).exists():
            return f
    raise SystemExit("no bold font found; edit FONTS in build.py")


def text_file(tmp: Path, name: str, text: str) -> str:
    p = tmp / f"{name}.txt"
    p.write_text(text)
    return str(p).replace(":", "\\:")


# ---------- voice ----------

def voiceover(tmp: Path, sid: str, text: str, engine: str, voice: str, speed: float) -> tuple[Path, float]:
    raw, wav = tmp / f"{sid}_raw.wav", tmp / f"{sid}.wav"
    rendered = HERE / "voice" / f"{sid}.wav"  # from video/tts.py, run in its own env
    if rendered.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", rendered, "-ar", "48000", "-ac", "2", wav])
        return wav, duration(wav)
    if engine == "kokoro":
        try:
            import numpy as np
            import soundfile as sf
            from kokoro import KPipeline
        except ImportError:
            engine = "say" if shutil.which("say") else "silent"
            print("  kokoro not installed (pip install kokoro soundfile); using", engine)
        else:
            if not _KOKORO:
                _KOKORO.append(KPipeline(lang_code="a"))
            chunks = [a.numpy() if hasattr(a, "numpy") else np.asarray(a)
                      for _, _, a in _KOKORO[0](text, voice=voice, speed=speed)]
            sf.write(raw, np.concatenate(chunks), 24000)
    if engine == "say":
        aiff = tmp / f"{sid}.aiff"
        run(["say", "-v", voice if " " in voice or voice[:3] not in ("af_", "am_", "bf_", "bm_") else "Samantha",
             "-o", aiff, text])
        raw = aiff
    if engine == "silent":  # not a Mac and no Kokoro: silent stand-in, for testing the edit only
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-t", f"{len(text.split()) / 160 * 60:.2f}", wav])
        return wav, duration(wav)
    run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-ar", "48000", "-ac", "2", wav])
    return wav, duration(wav)


# ---------- footage ----------

def mark_time(marks: list[dict], name: str) -> float:
    if name == "start":
        return next((m["start"] for m in marks if m["kind"] == "start"), 0.0)
    if name == "end":
        return next(m["start"] for m in marks if m["kind"] == "end")
    return next(m["start"] for m in marks if m["kind"] == "cut" and m["label"] == name)


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


def prep(phone: bool, src_scale: int = 1) -> str:
    """Any recording -> the 2x working frame (the phone clip is centred on the page colour).
    Playwright does not upscale: with a 2x video size it puts the page in the top-left quarter and fills the rest
    with grey, so that grey is cropped away first."""
    crop = f"crop=iw/{src_scale}:ih/{src_scale}:0:0," if src_scale > 1 else ""
    return crop + (f"scale=-2:{H2}:flags=lanczos,pad={W2}:{H2}:(ow-iw)/2:0:color={BG}" if phone
                   else f"scale={W2}:{H2}:flags=lanczos")


def close_up(box: dict, viewport: dict, phone: bool) -> str:
    """A still 16:9 crop around the box (CSS pixels from record.py), in working-frame pixels."""
    vw, vh = viewport["width"], viewport["height"]
    if phone:
        f = H2 / vh
        xoff = (W2 - round(vw * f / 2) * 2) / 2
    else:
        f, xoff = W2 / vw, 0
    x, y, w, h = xoff + box["x"] * f, box["y"] * f, box["width"] * f, box["height"] * f
    cw = min(max(w * 1.2, h * 1.2 * 16 / 9, W2 / 2.4), W2)
    ch = cw * 9 / 16
    cx = min(max(x + w / 2 - cw / 2, 0), W2 - cw)
    cy = min(max(y + h / 2 - ch / 2, 0), H2 - ch)
    ev = lambda v: int(v) // 2 * 2  # noqa: E731
    return f"crop={ev(cw)}:{ev(ch)}:{ev(cx)}:{ev(cy)}"


def focused_piece(clip: Path, a: float, b: float, focuses: list[dict], viewport: dict, phone: bool, out: Path,
                  src_scale: int = 1) -> Path:
    """Wide -> dissolve to a still close-up -> hold -> dissolve back to wide. No motion inside a shot, so no shake."""
    length = b - a
    shots, cur = [], 0.0
    for m in sorted(focuses, key=lambda m: m["start"]):
        t1, t2 = max(m["start"] - a, cur), min(m["start"] - a + m["hold"], length)
        if t2 - t1 < 1.0:
            continue
        if t1 - cur > 0.05:
            shots.append([cur, t1, None])
        shots.append([t1, t2, close_up(m["box"], viewport, phone)])
        cur = t2
    if length - cur > 0.05:
        shots.append([cur, length, None])
    # a sliver too short to dissolve through is merged into the shot before it
    merged = []
    for s in shots:
        if merged and s[1] - s[0] < XF + 0.15:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    n = len(merged)
    graph = [f"[0:v]trim=start={a:.2f}:end={b:.2f},setpts=PTS-STARTPTS,fps={FPS},{prep(phone, src_scale)},split={n}" +
             "".join(f"[b{i}]" for i in range(n))]
    for i, (s, e, crop) in enumerate(merged):
        tail = XF if i < n - 1 else 0
        f = f"[b{i}]trim=start={s:.2f}:end={min(e + tail, length):.2f},setpts=PTS-STARTPTS"
        f += f",{crop}" if crop else ""
        graph.append(f + f",scale={W}:{H}:flags=lanczos[s{i}]")
    last = "[s0]"
    for i in range(1, n):
        graph.append(f"{last}[s{i}]xfade=transition=fade:duration={XF}:offset={merged[i][0]:.2f}[x{i}]")
        last = f"[x{i}]"
    graph.append(f"{last}null[v]")
    return encode(["-i", clip, "-filter_complex", ";".join(graph), "-map", "[v]", "-an"], out)


def clip_scene(tmp: Path, sc: dict, clips: Path, target: float, fnt: str) -> Path:
    clip = clips / f"{sc['clip']}.webm"
    marks = json.loads((clips / f"{sc['clip']}.json").read_text())
    phone = sc.get("phone", False)
    meta = next((m for m in marks if m["kind"] == "meta"), None)
    viewport = meta["viewport"] if meta else ({"width": 390, "height": 844} if phone else {"width": W, "height": H})
    src_scale = meta.get("scale", 1) if meta else 1
    start, end = mark_time(marks, sc.get("from", "start")), mark_time(marks, sc.get("to", "end"))
    pieces = segments(marks, start, end)
    normal = sum(b - a for a, b, w in pieces if not w)
    waiting = sum(b - a for a, b, w in pieces if w)
    speed = min(max(waiting / max(target - normal, 2.0), 2.0), 24.0) if waiting else 1.0
    parts = []
    for i, (a, b, wait) in enumerate(pieces):
        out = tmp / f"{sc['id']}_{i}.mp4"
        focuses = [m for m in marks if m["kind"] == "focus" and a <= m["start"] < b and sc.get("zoom")]
        if focuses and not wait:
            parts.append(focused_piece(clip, a, b, focuses, viewport, phone, out, src_scale))
            continue
        s = speed if wait else 1.0
        vf = [f"trim=start={a:.2f}:end={b:.2f}", f"setpts=(PTS-STARTPTS)/{s:.3f}", f"fps={FPS}", prep(phone, src_scale),
              f"scale={W}:{H}:flags=lanczos"]
        if wait:
            label = text_file(tmp, f"{sc['id']}_{i}_w", f"sped up {s:.0f}x · real wait for the model")
            vf.append(f"drawtext=fontfile='{fnt}':textfile='{label}':fontsize=20:fontcolor=white:box=1:"
                      f"boxcolor=0x000000@0.55:boxborderw=10:x=w-tw-24:y=24")
        parts.append(encode(["-i", clip, "-vf", ",".join(vf), "-an"], out))
    lst = tmp / f"{sc['id']}_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    joined = tmp / f"{sc['id']}_joined.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    vf = []
    pad = max(0.0, target - duration(joined))
    if pad > 0:
        vf.append(f"tpad=stop_mode=clone:stop_duration={pad:.2f}")
    if sc.get("title"):
        tf = text_file(tmp, f"{sc['id']}_title", sc["title"])
        vf.append(f"drawtext=fontfile='{fnt}':textfile='{tf}':fontsize=28:fontcolor=white:box=1:boxcolor={BRAND}@0.92:"
                  f"boxborderw=14:x=28:y=24:alpha='min(t/0.4,1)'")
    print(f"  footage {normal:5.1f}s + waits {waiting:5.1f}s at {speed:.0f}x")
    return encode(["-i", joined, "-vf", ",".join(vf) or "null"], tmp / f"{sc['id']}.mp4")


# ---------- cards ----------

def card_scene(tmp: Path, sc: dict, target: float) -> Path:
    """Still stages of a card, dissolving into each other. Nothing moves, so nothing shakes."""
    stages = cards.render(sc["card"], tmp)
    weights = sc.get("stages") or [1] * len(stages)
    durs = [target * w / sum(weights) for w in weights]
    args, chain, last = [], [], "[0:v]"
    for p, d in zip(stages, durs):
        args += ["-loop", "1", "-framerate", FPS, "-t", f"{d + XF:.2f}", "-i", p]
    offset = 0.0
    for i in range(1, len(stages)):
        offset += durs[i - 1]
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={offset - XF / 2:.2f}[x{i}]")
        last = f"[x{i}]"
    chain.append(f"{last}fps={FPS},format=yuv420p,trim=duration={sum(durs):.2f}[v]")
    return encode([*args, "-filter_complex", ";".join(chain), "-map", "[v]"], tmp / f"{sc['id']}.mp4")


# ---------- captions ----------

def split_sentences(text: str) -> list[str]:
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch in ".?!" and len(cur.strip()) > 1:
            out.append(cur.strip())
            cur = ""
    out += [cur.strip()] if cur.strip() else []
    short = []
    for s in out:  # a caption over ~110 characters is split at the colon or comma nearest its middle
        while len(s) > 110:
            cuts = [i for i, c in enumerate(s) if c in ":," and 30 < i < len(s) - 30]
            if not cuts:
                break
            i = min(cuts, key=lambda k: abs(k - len(s) / 2))
            short.append(s[:i + 1].strip())
            s = s[i + 1:].strip()
        short.append(s)
    return short


def wrap(text: str, n: int = 62) -> str:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return "\n".join(lines + [cur])


def caption_cues(cues: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """One caption per sentence, timed by its share of the scene's voiceover."""
    out = []
    for start, dur, text in cues:
        sents = split_sentences(text)
        total, t = sum(len(s) for s in sents) or 1, start
        for s in sents:
            d = dur * len(s) / total
            out.append((t, t + d, s))
            t += d
    return out


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", type=Path)
    ap.add_argument("--tts", choices=["kokoro", "say"])
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--music", type=Path, default=HERE / "assets" / "music.mp3")
    ap.add_argument("--music-volume", type=float, default=0.10)
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE / "demo.mp4")
    a = ap.parse_args()
    cfg = json.loads((HERE / "narration.json").read_text())
    engine, voice, speed = a.tts or cfg["tts"], a.voice or cfg["voice"], a.speed or cfg["speed"]
    fnt = font()
    VENC[:] = pick_encoder()
    print("encoder:", VENC[1], "· voice:", engine, voice)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        scenes, cues, audio, t = [], [], [], 0.0
        for sc in cfg["scenes"]:
            wav, vo = voiceover(tmp, sc["id"], sc["text"], engine, voice, speed)
            target = vo + sc.get("tail", 0.9)
            print(f"{sc['id']}: voice {vo:5.1f}s")
            path = card_scene(tmp, sc, target) if sc.get("card") else clip_scene(tmp, sc, a.clips, target, fnt)
            d = duration(path)
            scenes.append(path)
            cues.append((t + 0.35, vo, sc["text"]))
            audio.append((wav, t + 0.35))
            t += d
        lst = tmp / "all.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in scenes))
        video = tmp / "video.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])

        caps = caption_cues(cues)
        if not a.no_captions:
            draws = []
            for i, (s, e, text) in enumerate(caps):
                tf = text_file(tmp, f"cap{i}", wrap(text))
                draws.append(f"drawtext=fontfile='{fnt}':textfile='{tf}':fontsize=26:fontcolor=white:line_spacing=6:"
                             f"box=1:boxcolor=0x000000@0.62:boxborderw=12:x=(w-tw)/2:y=h-th-34:"
                             f"enable='between(t,{s:.2f},{e:.2f})'")
            video = encode(["-i", video, "-vf", ",".join(draws)], tmp / "captioned.mp4")

        inputs, filters = [], []
        for i, (wav, at) in enumerate(audio):
            inputs += ["-i", wav]
            ms = int(at * 1000)
            filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        mix = "".join(f"[a{i}]" for i in range(len(audio)))
        filters.append(f"{mix}amix=inputs={len(audio)}:normalize=0,apad,atrim=0:{t:.2f}[vo]")
        if a.music and a.music.exists():
            n = len(audio)
            inputs += ["-stream_loop", "-1", "-i", a.music]
            filters.append(f"[{n}:a]atrim=0:{t:.2f},volume={a.music_volume},afade=t=in:d=2,"
                           f"afade=t=out:st={max(t - 4, 0):.2f}:d=4[mu]")
            filters.append("[vo][mu]amix=inputs=2:normalize=0:duration=first[out]")
            out_label = "[out]"
            print("music:", a.music.name)
        else:
            out_label = "[vo]"
            print("music: none (put a track at video/assets/music.mp3 or pass --music)")
        track = tmp / "audio.m4a"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters), "-map", out_label,
             "-c:a", "aac", "-b:a", "192k", track])
        run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", track, "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", a.out])
    a.out.with_suffix(".srt").write_text("\n".join(f"{i + 1}\n{srt_time(s)} --> {srt_time(e)}\n{x}\n"
                                                   for i, (s, e, x) in enumerate(caps)))
    total = duration(a.out)
    print(f"\n{a.out}  {total:.1f}s" + ("" if total <= MAX_TOTAL else f"  <-- OVER {MAX_TOTAL:.0f}s: shorten a scene's text"))


if __name__ == "__main__":
    main()
