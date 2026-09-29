"""Drug name -> RxNorm RXCUI -> NDC list, via the free NLM RxNav API (cached on disk)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

RXNAV = "https://rxnav.nlm.nih.gov/REST"
CACHE = Path(__file__).resolve().parents[2] / "data" / "processed" / "rxnav_cache.json"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def lookup(name: str) -> dict:
    """Return {"rxcui": str, "ndcs": [str]} for an RxNorm drug name like 'lisinopril 10 MG Oral Tablet'."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if name not in cache:
        q = urllib.parse.quote(name)
        ids = _get(f"{RXNAV}/rxcui.json?name={q}&search=2").get("idGroup", {}).get("rxnormId") or []
        if not ids:
            raise LookupError(f"RxNorm could not find '{name}'")
        ndcs = _get(f"{RXNAV}/rxcui/{ids[0]}/ndcs.json").get("ndcGroup", {}).get("ndcList", {}).get("ndc") or []
        cache[name] = {"rxcui": ids[0], "ndcs": ndcs}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1))
    return cache[name]
