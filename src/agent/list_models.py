"""List every model this Token Factory key can use, then probe which ones accept image input.

Run from the repo root:  python3 src/agent/list_models.py
Each probe sends a 1x1 red pixel (a few tokens; cost is negligible).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hello_nemotron import ROOT, load_env  # noqa: E402

RED_PIXEL = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")
VISION_HINTS = ("vl", "vision", "omni", "gemma-3", "kimi", "llava", "pixtral", "qwen2.5-vl", "qwen3-vl", "llama-4", "minicpm-v", "qwen3.8")


def req(method: str, url: str, key: str, body: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:  # timeouts etc.
        return 0, str(e)[:200]


def main() -> None:
    load_env(ROOT / ".env")
    key = os.environ["NEBIUS_API_KEY"]
    base = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"

    _, data = req("GET", f"{base}/models", key)
    ids = sorted(m["id"] for m in data.get("data", []))
    print(f"{len(ids)} models available:")
    for i in ids:
        print("  -", i)

    candidates = [i for i in ids if any(h in i.lower() for h in VISION_HINTS)]
    print(f"\nProbing image input on {len(candidates)} likely vision models...")
    for m in candidates:
        code, out = req("POST", f"{base}/chat/completions", key, {
            "model": m, "max_tokens": 300, "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "What color is this image? One word."},
                {"type": "image_url", "image_url": {"url": RED_PIXEL}}]}]})
        if code == 200:
            ans = (out["choices"][0]["message"].get("content") or "").strip()
            print(f"  [VISION OK] {m} -> {ans!r}")
        else:
            print(f"  [no]        {m} (HTTP {code})")


if __name__ == "__main__":
    main()
