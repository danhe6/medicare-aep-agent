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
    # photos / scans (transcription only). Nemotron VL matched or beat Gemma 3 27B on the 46-letter eval (10/18):
    # type 45/46 both, deadlines 33/33 both, key item 42/42 vs 41/42, median 4.1 s vs 5.6 s per letter.
    "vision": os.environ.get("MODEL_VISION", "nvidia/Nemotron-3.5-Super-VL"),
}


# Extraction is a small JSON fill-in: Nemotron's thinking mode spent ~3,700 tokens (25 s) on one label.
NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}


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
    from agent.metrics import MeteredClient
    return MeteredClient(OpenAI(base_url=base, api_key=os.environ["NEBIUS_API_KEY"], max_retries=3, timeout=120))
