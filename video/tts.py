"""Render the voiceover with Kokoro (open-source TTS, Apache 2.0) into video/voice/<scene>.wav.
build.py uses these files when they exist. Run it in its own env, so Kokoro's PyTorch never touches the app's:

    conda create -y -n tts python=3.11 && conda activate tts
    pip install "torch==2.2.2" "transformers<4.48" "numpy<2" "kokoro>=0.9.4" soundfile
    python video/tts.py                      # every scene, voice from narration.json
    python video/tts.py --voice am_michael   # try another voice
    python video/tts.py --only hook,s2       # redo some scenes
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

HERE = Path(__file__).parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--only")
    a = ap.parse_args()
    cfg = json.loads((HERE / "narration.json").read_text())
    voice, speed = a.voice or cfg["voice"], a.speed or cfg.get("speed", 1.0)
    only = set(a.only.split(",")) if a.only else None
    out = HERE / "voice"
    out.mkdir(exist_ok=True)
    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    for sc in cfg["scenes"]:
        if only and sc["id"] not in only:
            continue
        chunks = [c.numpy() if hasattr(c, "numpy") else np.asarray(c) for _, _, c in pipe(sc["text"], voice=voice, speed=speed)]
        audio = np.concatenate(chunks)
        sf.write(out / f"{sc['id']}.wav", audio, 24000)
        print(f"{sc['id']}: {len(audio) / 24000:5.1f}s  {voice}")
