"""Is her doctor in a plan's network?  Best-effort evidence, never a guarantee.

    PYTHONPATH=src python -m network.doctor "Maria Lopez" Florida Miami "CarePlus Health Plans, Inc."

1. NPPES NPI Registry (CMS, free, no key): confirms the doctor exists, specialty and practice address.
2. Tavily web search (TAVILY_API_KEY): looks for the doctor on each insurer's provider directory pages.
Online directories are often out of date, so the answer is always "evidence found / not found - call to confirm".
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

from agent.llm import _load_env  # reads .env

NPPES = "https://npiregistry.cms.hhs.gov/api/?version=2.1&limit=10&enumeration_type=NPI-1"
TAVILY = "https://api.tavily.com/search"
TIMEOUT = 20

STATE_CODES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
               "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "washington d.c.": "DC", "florida": "FL",
               "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
               "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
               "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
               "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
               "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
               "puerto rico": "PR", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
               "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
               "wisconsin": "WI", "wyoming": "WY", "guam": "GU", "virgin islands": "VI", "american samoa": "AS",
               "northern mariana islands": "MP"}


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        return json.load(r)


def find_doctor(name: str, state: str | None = None, city: str | None = None) -> list[dict]:
    parts = [p for p in re.sub(r"^(dr\.?|doctor)\s+", "", name.strip(), flags=re.I).replace(",", " ").split() if p]
    if not parts:
        return []
    q = {"last_name": parts[-1]}
    if len(parts) > 1:
        q["first_name"] = parts[0] + "*"
    if state:
        q["state"] = STATE_CODES.get(state.lower(), state[:2].upper())
    if city:
        q["city"] = city
    out = []
    for r in _get(NPPES + "&" + urllib.parse.urlencode(q)).get("results", []):
        b = r.get("basic", {})
        addr = next((a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"), {})
        tax = next((t for t in r.get("taxonomies", []) if t.get("primary")), {})
        out.append({"npi": r.get("number"), "name": f"{b.get('first_name', '').title()} {b.get('last_name', '').title()}".strip(),
                    "credential": b.get("credential"), "specialty": tax.get("desc"),
                    "city": (addr.get("city") or "").title(), "state": addr.get("state"),
                    "phone": addr.get("telephone_number")})
    return out


def _tavily(query: str) -> list[dict]:
    _load_env()
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    body = json.dumps({"api_key": key, "query": query, "max_results": 5, "search_depth": "advanced"}).encode()
    req = urllib.request.Request(TAVILY, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r).get("results", [])


def _insurer_words(org: str) -> list[str]:
    stop = {"inc", "health", "plan", "plans", "insurance", "company", "of", "the", "llc", "corp", "corporation", "co"}
    return [w for w in re.findall(r"[a-z]+", org.lower()) if w not in stop and len(w) > 2]


_SUFFIXES = {"", "health", "healthplans", "healthplan", "hp", "plans", "plan", "insurance", "medicare"}


def _is_insurer_domain(url: str, words: list[str]) -> bool:
    """leonhealth.com matches 'leon'; dr-leonardo.com does not."""
    labels = re.split(r"[.-]", urllib.parse.urlparse(url).netloc.lower())
    return any(lab.startswith(w) and (lab[len(w):] in _SUFFIXES or lab[len(w):].startswith(("health", "plans")))
               for lab in labels for w in words)


def _names(doctor: str) -> tuple[str, str]:
    parts = [re.sub(r"[^a-z-]", "", p) for p in re.sub(r"^(dr\.?|doctor)\s+", "", doctor.strip().lower()).replace(",", " ").split()]
    parts = [p for p in parts if p and p not in ("md", "do", "pa", "np", "dr")]
    return (parts[0] if len(parts) > 1 else ""), (parts[-1] if parts else "")


def _mentions(text: str, first: str, last: str) -> bool:
    """Full-name match only ("maria lopez", "lopez, maria", "lopez maria"), never the surname alone."""
    if not last:
        return False
    if not first:
        return bool(re.search(rf"\b{re.escape(last)}\b", text))
    return bool(re.search(rf"\b{re.escape(first)}\b[\w. ]{{0,12}}\b{re.escape(last)}\b|\b{re.escape(last)}\b,?\s+{re.escape(first)}\b", text))


def _year(*texts: str) -> int | None:
    years = [int(y) for t in texts for y in re.findall(r"\b(20[12]\d)\b", t or "")]
    return max(years) if years else None


def check(doctor: str, state: str, city: str | None, organizations: list[str], specialty: str | None = None,
          current_year: int = 2026) -> dict:
    """For each insurer: web evidence that the doctor is listed in its network. Never claims certainty."""
    try:
        npi = find_doctor(doctor, state, city)
    except Exception:  # registry unreachable: continue with web search only
        npi = []
    if specialty:
        npi = [m for m in npi if specialty.lower() in (m.get("specialty") or "").lower()] or npi
    kinds = {(m.get("specialty"), m.get("city")) for m in npi}
    if len(kinds) > 1 and not specialty:
        return {"needs_clarification": True, "npi_registry_matches": npi[:5],
                "ask": "Several clinicians have this name. Ask which one (specialty and city), then call again with specialty."}
    first, last = _names(doctor)
    results = []
    for org in list(dict.fromkeys(organizations))[:5]:
        words = _insurer_words(org)
        try:
            hits = _tavily(f'"{first} {last}" {specialty or ""} {city or ""} {state} {org} provider directory {current_year}')
        except Exception as e:
            return {"error": f"Web search unavailable ({e}). Tell the user to call the plan or use its online directory."}
        evidence = []
        for h in hits:
            text = (h.get("title", "") + " " + h.get("content", "")).lower()
            url = h.get("url", "")
            if not _mentions(text, first, last):
                continue
            on_insurer_site = _is_insurer_domain(url, words)
            if not (on_insurer_site or any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)):
                continue
            yr = _year(url, h.get("title", ""))
            evidence.append({"url": url, "title": h.get("title"), "snippet": (h.get("content") or "")[:300],
                             "on_insurer_website": on_insurer_site, "directory_year": yr,
                             "current": yr is None or yr >= current_year})
        if any(e["on_insurer_website"] and e["current"] for e in evidence):
            status = "listed_online"
        elif any(e["on_insurer_website"] for e in evidence):
            status = "listed_in_older_directory"
        elif evidence:
            status = "mentioned_online"
        else:
            status = "no_evidence_found"
        results.append({"organization": org, "status": status, "evidence": evidence[:3]})
    return {"doctor_query": doctor, "npi_registry_matches": npi[:3], "plans": results,
            "how_to_read": "listed_online = full name found in the insurer's own current directory; "
                           "listed_in_older_directory = found only in a past year's directory; mentioned_online = "
                           "found elsewhere; no_evidence_found does NOT mean out of network. Directories are often "
                           "out of date: call the plan (or the doctor's office) to confirm before enrolling.",
            "source": "NPPES NPI Registry (CMS) + Tavily web search"}


if __name__ == "__main__":
    doc, st, city, *orgs = sys.argv[1:]
    print(json.dumps(check(doc, st, city, orgs), indent=1))
