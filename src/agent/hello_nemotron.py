"""Day 1 smoke test: confirm the Nebius Token Factory key works and Nemotron responds.

Run from the repo root:  python3 src/agent/hello_nemotron.py
Standard library only; no installs needed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path) -> None:
    if not path.exists():
        sys.exit(f"Missing {path}. Copy .env.example to .env and add NEBIUS_API_KEY.")
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def call(method: str, url: str, key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {url}: {e.read().decode()[:500]}")


def main() -> None:
    load_env(ROOT / ".env")
    key = os.environ.get("NEBIUS_API_KEY", "")
    if not key:
        sys.exit("NEBIUS_API_KEY is empty in .env")
    base = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    model = os.environ.get("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")

    # 1) Which Nemotron models can this key use?
    models = [m["id"] for m in call("GET", f"{base}/models", key).get("data", [])]
    nemotron = sorted(m for m in models if "nemotron" in m.lower())
    print("Nemotron models available:")
    for m in nemotron:
        print("  -", m)
    if model not in models:
        print(f"\nWARNING: {model} not in the list; update NEBIUS_MODEL in .env.")
        return

    # 2) One real call
    resp = call("POST", f"{base}/chat/completions", key, {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise Medicare assistant."},
            {"role": "user", "content": "In two sentences: what is the Medicare Annual Enrollment Period and when does it run?"},
        ],
        "max_tokens": 400,
        "temperature": 0.2,
    })
    msg = resp["choices"][0]["message"]
    print(f"\nModel: {model}\n")
    print(msg.get("content") or msg)
    print("\nUsage:", resp.get("usage"))
    print("\nDay 1 check passed.")


if __name__ == "__main__":
    main()
