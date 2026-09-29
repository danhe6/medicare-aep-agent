"""Operational metrics for every AI task: named, versioned, timed, token-counted. NO health content is recorded.

Each line of logs/metrics.jsonl = one model call or one tool call:
  {"t", "run", "task", "version", "kind": "llm"|"tool", "model", "prompt_tokens", "completion_tokens",
   "latency_ms", "ok"}
`run` = a random id per chat turn, so a turn's calls can be grouped. Summarize with pipeline/metrics_report.py.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

LOG = Path(__file__).resolve().parents[2] / "logs" / "metrics.jsonl"

# Every AI task has a name and a version. Bump the version when its prompt or model changes.
TASKS = {
    "agent.turn": "v5",            # Nemotron Super: tool calling + plain-language answer
    "notice.transcribe": "v1",     # vision model: care-ending notice photo -> text
    "notice.extract": "v2",        # Nemotron Lightning (fallback Super): notice text -> fields
    "label.transcribe": "v1",      # vision model: pill-bottle label photo -> text
    "label.extract": "v1",         # Nemotron Lightning (fallback Super): label text -> fields
}

_state = threading.local()
_lock = threading.Lock()


def _write(rec: dict) -> None:
    if os.environ.get("METRICS_LOG", "1") == "0":
        return
    LOG.parent.mkdir(exist_ok=True)
    line = json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec})
    with _lock, open(LOG, "a") as f:
        f.write(line + "\n")


def set_run(run_id: str | None) -> None:
    """Tag the calls that follow with this chat turn's id. Call it right before each model/tool call: the
    streaming generator may resume on a different worker thread between events."""
    _state.run = run_id


def new_run_id() -> str:
    return uuid.uuid4().hex[:10]


@contextlib.contextmanager
def run():
    """One chat turn."""
    prev = getattr(_state, "run", None)
    _state.run = uuid.uuid4().hex[:10]
    try:
        yield _state.run
    finally:
        _state.run = prev


@contextlib.contextmanager
def task(name: str):
    stack = getattr(_state, "tasks", None) or []
    _state.tasks = stack + [name]
    try:
        yield
    finally:
        _state.tasks = stack


def current_task() -> str:
    stack = getattr(_state, "tasks", None) or []
    return stack[-1] if stack else "untagged"


def record_tool(name: str, latency_ms: float, ok: bool) -> None:
    _write({"run": getattr(_state, "run", None), "task": f"tool.{name}", "version": "", "kind": "tool",
            "latency_ms": round(latency_ms), "ok": ok})


class _Completions:
    def __init__(self, inner):
        self._inner = inner

    def create(self, **kw):
        name = current_task()
        t0 = time.perf_counter()
        ok = False
        usage = None
        try:
            resp = self._inner.create(**kw)
            usage = getattr(resp, "usage", None)
            ok = True
            return resp
        finally:
            _write({"run": getattr(_state, "run", None), "task": name, "version": TASKS.get(name, ""),
                    "kind": "llm", "model": kw.get("model"),
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "latency_ms": round((time.perf_counter() - t0) * 1000), "ok": ok})


class _Chat:
    def __init__(self, inner):
        self.completions = _Completions(inner.completions)


class MeteredClient:
    """Drop-in wrapper around the OpenAI client: same .chat.completions.create, plus a metrics line per call."""
    def __init__(self, inner):
        self._inner = inner
        self.chat = _Chat(inner.chat)

    def __getattr__(self, name):
        return getattr(self._inner, name)
