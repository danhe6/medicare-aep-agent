"""Simple in-memory rate limits, so a public URL can't run up the model bill or crowd out real users.

One process, no database: counters reset on restart, which is fine for a single small VM.
  * per visitor (IP): a burst limit per minute and a daily limit, per kind of request
  * whole site: a daily cap on AI chat turns, and a hard daily cap on model spend (DAILY_SPEND_CAP_USD, from the
    token counts the metrics wrapper already records and pipeline/model_prices.json)
All numbers can be changed with environment variables (see LIMITS).
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from agent import metrics


def _env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# kind -> (per minute, per day) for one visitor
LIMITS = {
    "chat":   (_env("RL_CHAT_MIN", 12), _env("RL_CHAT_DAY", 200)),
    "upload": (_env("RL_UPLOAD_MIN", 6), _env("RL_UPLOAD_DAY", 40)),
    "lookup": (_env("RL_LOOKUP_MIN", 60), _env("RL_LOOKUP_DAY", 2000)),
    "session": (_env("RL_SESSION_MIN", 10), _env("RL_SESSION_DAY", 200)),
}
SITE_CHAT_DAY = _env("RL_SITE_CHAT_DAY", 5000)   # all visitors together; ~$10/day at ~$0.002 a turn
def spend_cap() -> float:
    """Hard budget: model spend per UTC day, in USD (read on each call so .env changes apply after a restart)."""
    try:
        return float(os.environ.get("DAILY_SPEND_CAP_USD", "10"))
    except ValueError:
        return 10.0

MESSAGES = {
    "en": {"visitor": "You're going a little fast. Please wait a minute and try again.",
           "site": "The helper is very busy today. Please try again tomorrow, or call 1-800-MEDICARE."},
    "es": {"visitor": "Va un poco rápido. Espere un minuto e intente de nuevo.",
           "site": "El asistente está muy ocupado hoy. Intente mañana, o llame al 1-800-MEDICARE."},
}

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = {}
_site = {"day": "", "chat": 0}


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind Caddy the app is reachable only through the proxy (compose `expose`, no published
    port), so the first X-Forwarded-For entry is the real visitor."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request: Request, kind: str, lang: str = "en") -> None:
    """Raise 429 if this visitor (or the whole site, for chat) is over its limit; otherwise count the request."""
    msg = MESSAGES.get(lang, MESSAGES["en"])
    per_min, per_day = LIMITS[kind]
    now = time.time()
    key = (client_ip(request), kind)
    with _lock:
        today = time.strftime("%Y-%m-%d", time.gmtime(now))
        if _site["day"] != today:
            _site.update(day=today, chat=0)
            _hits.clear()  # daily windows restart; also keeps memory bounded
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > 86400:
            q.popleft()
        last_min = sum(1 for t in q if now - t < 60)
        if last_min >= per_min or len(q) >= per_day:
            raise HTTPException(429, msg["visitor"], headers={"Retry-After": "60"})
        if kind in ("chat", "upload") and metrics.spend_today() >= spend_cap():
            raise HTTPException(429, msg["site"], headers={"Retry-After": "3600"})
        if kind == "chat":
            if _site["chat"] >= SITE_CHAT_DAY:
                raise HTTPException(429, msg["site"], headers={"Retry-After": "3600"})
            _site["chat"] += 1
        q.append(now)
