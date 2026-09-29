"""Nebius Token Factory client (OpenAI-compatible) with Nemotron model roles."""
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
MODELS = {
    "agent": os.environ.get("MODEL_AGENT", "nvidia/nemotron-3-super-120b-a12b"),      # tool calling / planning
    "reason": os.environ.get("MODEL_REASON", "nvidia/Nemotron-3-Ultra-550b-a55b"),     # hard reasoning (traps)
    "extract": os.environ.get("MODEL_EXTRACT", "nvidia/Nemotron-3_5-Lightning"),       # cheap extraction
    "vision": os.environ.get("MODEL_VISION", "google/gemma-3-27b-it"),                 # photos / scans (OCR only)
}


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def client() -> OpenAI:
    _load_env()
    base = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return OpenAI(base_url=base, api_key=os.environ["NEBIUS_API_KEY"], max_retries=3, timeout=120)
