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
CACHE_VERSION = 3  # 3: exact name match first (search=2 sent an IR metformin name to the ER product)


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
    ids = _get(f"{RXNAV}/rxcui.json?name={q}&search=0").get("idGroup", {}).get("rxnormId") or []
    if not ids:  # not an exact RxNorm name: normalized match, then approximate
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


def search(term: str, limit: int = 5) -> list[dict]:
    """Free-text drug search (e.g. 'eliquis 5', 'metformin 500mg'): best RxNorm clinical/brand drug matches."""
    q = urllib.parse.quote(term)
    cands = _get(f"{RXNAV}/approximateTerm.json?term={q}&maxEntries=25").get("approximateGroup", {}).get("candidate") or []
    out, seen = [], set()
    for c in cands:
        if c["rxcui"] in seen:
            continue
        seen.add(c["rxcui"])
        props = _get(f"{RXNAV}/rxcui/{c['rxcui']}/properties.json").get("properties") or {}
        if props.get("tty") in ("SCD", "SBD"):  # a specific strength + dose form
            out.append({"rxnorm_name": props["name"], "rxcui": c["rxcui"],
                        "type": "brand" if props["tty"] == "SBD" else "generic"})
        if len(out) >= limit:
            break
    return out


def exact_rxcui(name: str) -> str | None:
    """RXCUI only if `name` is an exact RxNorm name (no fuzzy matching) - used to reject invented names."""
    q = urllib.parse.quote(name)
    ids = _get(f"{RXNAV}/rxcui.json?name={q}&search=0").get("idGroup", {}).get("rxnormId") or []
    return ids[0] if ids else None


# ---- autocomplete (search-as-you-type) ----
NAMES = CACHE.parent / "rxnav_displaynames.json"
_names: list[str] | None = None


def display_names() -> list[str]:
    """All RxNorm display names (drug + brand names, ~30k), downloaded once from RxNav and kept on disk."""
    global _names
    if _names is None:
        if NAMES.exists():
            _names = json.loads(NAMES.read_text())
        else:
            terms = _get(f"{RXNAV}/displaynames.json").get("displayTermsList", {}).get("term") or []
            _names = sorted({t.strip() for t in terms if t and t.strip()}, key=str.lower)
            NAMES.parent.mkdir(parents=True, exist_ok=True)
            NAMES.write_text(json.dumps(_names))
    return _names


SALTS = {"calcium", "sodium", "potassium", "magnesium", "hydrochloride", "hcl", "hydrobromide", "anhydrous", "monohydrate",
         "dihydrate", "trihydrate", "hemihydrate", "solvate", "mesylate", "maleate", "besylate", "succinate", "tartrate",
         "fumarate", "citrate", "acetate", "sulfate", "phosphate", "bromide", "chloride", "propylene", "glycol", "free", "base"}


def _clean(n: str, names: set[str]) -> bool:
    """Keep plain drug and brand names; drop dose packs/kits ('... 0.5 mg (28) tablet') and salt spellings of a
    drug that is already listed ('atorvastatin calcium trihydrate' when 'atorvastatin' exists)."""
    low = n.lower()
    if any(ch.isdigit() for ch in low) or " pack" in low or " kit" in low or "(" in low:
        return False
    words = low.replace("/", " ").split()
    if len(words) > 1 and any(w in SALTS for w in words[1:]) and words[0] in names:
        return False
    return True


def suggest(q: str, limit: int = 8) -> list[str]:
    """Names starting with what was typed first, then names containing it as a word ('glar' -> insulin glargine)."""
    q = q.strip().lower()
    if len(q) < 2:
        return []
    names = display_names()
    lower = {n.lower() for n in names}
    hits = [n for n in names if (n.lower().startswith(q) or f" {q}" in f" {n.lower()}") and _clean(n, lower)]
    hits.sort(key=lambda n: (not n.lower().startswith(q), len(n), n.lower()))
    return [h[:1].upper() + h[1:].lower() for h in hits[:limit]]  # drop tall-man caps (metFORMIN)


def products(name: str) -> list[dict]:
    """Every strength and form of a drug name: [{rxnorm_name, rxcui, type: brand|generic}] (RxNav /drugs)."""
    cache = _load()
    key = f"products:{name.lower()}"
    if key in cache:
        return cache[key]
    groups = _get(f"{RXNAV}/drugs.json?name={urllib.parse.quote(name)}").get("drugGroup", {}).get("conceptGroup") or []
    out = []
    for g in groups:
        if g.get("tty") not in ("SBD", "SCD"):
            continue
        for c in g.get("conceptProperties") or []:
            out.append({"rxnorm_name": c["name"], "rxcui": c["rxcui"], "type": "brand" if g["tty"] == "SBD" else "generic"})
    cache[key] = out
    _save(cache)
    return out


def products_for(name: str) -> list[dict]:
    """products(), narrowed to the name that was picked: a brand ('Eliquis') -> that brand's products; an ingredient
    ('atorvastatin') -> its single-ingredient products, generic and brand (Lipitor), not combinations (Caduet)."""
    import re
    n = name.strip().lower()
    items = products(name)
    brand = [x for x in items if re.search(r"\[([^\]]+)\]$", x["rxnorm_name"]) and
             re.search(r"\[([^\]]+)\]$", x["rxnorm_name"]).group(1).lower() == n]
    if brand:
        return brand
    slashes = n.count(" / ")
    bare = lambda r: re.sub(r"^\d+(?:\.\d+)? (ml|actuat|hr|day) ", "", r.lower())  # "3 ML insulin glargine ... Pen"
    return [x for x in items if bare(x["rxnorm_name"]).startswith(n + " ") and x["rxnorm_name"].count(" / ") == slashes]
