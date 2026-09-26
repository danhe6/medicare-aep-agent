"""Drug name -> RxNorm concept (RXCUI, NDCs, brand/generic, equivalent forms, generic alternative).

Uses the free NLM RxNav API; everything is cached in data/processed/rxnav_cache.json.
  * equivalents: quantified / unquantified forms of the same drug (e.g. "insulin glargine ... Pen Injector
    [Lantus]" vs "3 ML insulin glargine ... Pen Injector [Lantus]") - formularies may list either one.
  * generic: for a brand product (TTY SBD), the matching generic clinical drug (TTY SCD), if one exists.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

RXNAV = "https://rxnav.nlm.nih.gov/REST"
CACHE = Path(__file__).resolve().parents[2] / "data" / "processed" / "rxnav_cache.json"
CACHE_VERSION = 2


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _load() -> dict:
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def _save(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))


def _related(rxcui: str, **params) -> list[dict]:
    q = urllib.parse.urlencode(params)
    groups = _get(f"{RXNAV}/rxcui/{rxcui}/related.json?{q}").get("relatedGroup", {}).get("conceptGroup") or []
    return [c for g in groups for c in (g.get("conceptProperties") or [])]


def _concept(rxcui: str) -> dict:
    props = _get(f"{RXNAV}/rxcui/{rxcui}/properties.json").get("properties") or {}
    ndcs = _get(f"{RXNAV}/rxcui/{rxcui}/ndcs.json").get("ndcGroup", {}).get("ndcList", {}).get("ndc") or []
    equiv = {c["rxcui"] for rela in ("has_quantified_form", "quantified_form_of")
             for c in _related(rxcui, rela=rela)} - {rxcui}
    for e in list(equiv):  # NDCs are attached to the quantified form
        ndcs += _get(f"{RXNAV}/rxcui/{e}/ndcs.json").get("ndcGroup", {}).get("ndcList", {}).get("ndc") or []
    return {"rxcui": rxcui, "name": props.get("name"), "tty": props.get("tty"),
            "ndcs": sorted(set(ndcs)), "equivalents": sorted(equiv)}


def lookup(name: str) -> dict:
    """Return {rxcui, name, tty, ndcs, equivalents, generic} for an RxNorm drug name."""
    cache = _load()
    hit = cache.get(name)
    if hit and hit.get("v") == CACHE_VERSION:
        return hit
    q = urllib.parse.quote(name)
    ids = _get(f"{RXNAV}/rxcui.json?name={q}&search=2").get("idGroup", {}).get("rxnormId") or []
    if not ids:
        cands = _get(f"{RXNAV}/approximateTerm.json?term={q}&maxEntries=1") \
            .get("approximateGroup", {}).get("candidate") or []
        ids = [cands[0]["rxcui"]] if cands else []
    if not ids:
        raise LookupError(f"RxNorm could not find '{name}'")
    info = _concept(ids[0])
    info["generic"] = None
    if info["tty"] == "SBD":  # brand product -> generic clinical drug
        scd = _related(info["rxcui"], tty="SCD")
        if scd:
            info["generic"] = _concept(scd[0]["rxcui"])
    info["v"] = CACHE_VERSION
    cache[name] = info
    _save(cache)
    return info
