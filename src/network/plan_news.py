"""Is this plan (or insurer) leaving Medicare next year? Tavily news search, with sources, never a guess.

Insurers send non-renewal letters in early October and exits make local news (Humana alone: about 600,000 members for
2027). CMS data is checked first in tools.check_current_plan (a plan with no next-year row may be ending); this adds
what the news says, filtered in code so only articles that name the insurer, an exit and the year are kept.
Every article is returned with its title, site and link; the agent may only report an exit it can cite.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from urllib.parse import urlsplit

from agent.llm import _load_env

TAVILY = "https://api.tavily.com/search"
EXIT = re.compile(r"\b(exit(?:s|ing)?|non-?renew\w*|leav(?:e|es|ing) (?:the )?(?:medicare|market|county|counties|state)|"
                  r"discontinu\w+|terminat\w+|will not (?:be )?offer\w*|won't (?:be )?offer\w*|pull(?:s|ing)? out|"
                  r"no longer (?:be )?(?:offer\w*|available))\b", re.I)
_CACHE: dict = {}
TTL = 12 * 3600
STOP = {"inc", "inc.", "company", "corporation", "corp", "of", "the", "health", "plan", "plans", "insurance", "healthcare",
        "medicare", "advantage", "llc", "group", "services", "medical", "care", "holdings", "systems", "benefit"}


def _short(org: str) -> str:
    """'Humana Medical Plan, Inc.' -> 'Humana'; keeps the distinctive words for search and matching."""
    words = [w for w in re.split(r"[\s,]+", org or "") if w and w.lower() not in STOP]
    return " ".join(words[:2]) or (org or "")


def _search(query: str) -> list[dict]:
    _load_env()
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    body = json.dumps({"api_key": key, "query": query, "topic": "news", "days": 200, "max_results": 8,
                       "search_depth": "advanced"}).encode()
    req = urllib.request.Request(TAVILY, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("results", [])


def _key_sentence(text: str, insurer: str) -> str:
    """The sentence that says the exit (page text often starts with menus and captions)."""
    text = re.sub(r"\s+", " ", text or "")
    first = insurer.split()[0].lower() if insurer else ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if EXIT.search(s) and first in s.lower() and 30 < len(s) < 400:
            return s.strip()
    return next((s.strip() for s in sentences if EXIT.search(s) and 30 < len(s) < 400), text[:260])


def relevant(article: dict, insurer: str, year: int) -> bool:
    """Code decides what counts: the insurer, an exit word and the year must all appear."""
    text = f"{article.get('title', '')} {article.get('content', '')}"
    first = insurer.split()[0].lower() if insurer else ""
    return bool(first) and first in text.lower() and bool(EXIT.search(text)) and str(year) in text


def plan_news(organization: str, year: int, state: str | None = None, plan_name: str | None = None,
              search=_search) -> dict:
    insurer = _short(organization)
    key = (insurer.lower(), (state or "").lower(), year)
    if key in _CACHE and time.time() - _CACHE[key][0] < TTL:
        return _CACHE[key][1]
    queries = [f"{insurer} Medicare Advantage plans {year} exit non-renewal {state or ''}".strip()]
    if plan_name:
        queries.append(f'"{plan_name}" {year} plan ending Medicare')
    seen, articles = set(), []
    try:
        for q in queries:
            for a in search(q):
                url = a.get("url", "")
                if url in seen or not relevant(a, insurer, year):
                    continue
                seen.add(url)
                snippet = _key_sentence(a.get("content", ""), insurer)
                articles.append({"title": a.get("title", "")[:160], "site": urlsplit(url).netloc.removeprefix("www."),
                                 "url": url, "published": a.get("published_date"), "snippet": snippet})
    except Exception as e:  # noqa: BLE001 - news is extra context; the answer stands without it
        return {"insurer": insurer, "year": year, "articles": [], "searched": False, "error": str(e)[:120]}
    out = {"insurer": insurer, "year": year, "state": state, "articles": articles[:4], "searched": True,
           "found_exit_news": bool(articles),
           "how_to_use": "News is a lead, not proof for one plan. Name the source. The plan's own letter (sent in early "
                         "October) and Medicare.gov are the authority; a plan without a next-year row in CMS data may be "
                         "ending or renumbered."}
    _CACHE[key] = (time.time(), out)
    return out
