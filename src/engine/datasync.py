"""Keep data/releases in sync with the newest data release published on GitHub.

    python -m engine.datasync        (PYTHONPATH=src)

The app calls ensure_current() at startup. Downloads only when a newer release exists; writes to a temp
folder and switches CURRENT atomically, so a failed download never breaks the running app.
Env: DATA_REPO (default danhe6/medicare-aep-agent), GITHUB_TOKEN (needed while the repo is private).
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path

RELEASES = Path(__file__).resolve().parents[2] / "data" / "releases"
PREFIX = "data-"
FILES = ("manifest.json", "plan_info.parquet", "geo.parquet", "formulary.parquet", "bene_cost.parquet",
         "insulin_cost.parquet", "pricing.parquet", "landscape.parquet")
OPTIONAL = ("mfp.parquet", "hist_plan_years.parquet", "hist_formulary_changes.parquet",
            "hist_plan_map.parquet", "hist_contract_stability.parquet")


def _req(url: str, accept: str = "application/vnd.github+json") -> urllib.request.Request:
    h = {"Accept": accept, "User-Agent": "medicare-aep-agent"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return urllib.request.Request(url, headers=h)


def latest_release(repo: str) -> dict | None:
    with urllib.request.urlopen(_req(f"https://api.github.com/repos/{repo}/releases?per_page=30"), timeout=60) as r:
        rels = [x for x in json.load(r) if x["tag_name"].startswith(PREFIX) and not x["draft"]]
    return max(rels, key=lambda x: x["published_at"]) if rels else None


def ensure_current(repo: str | None = None) -> str:
    """Make CURRENT point at the newest published data release. Returns the release id."""
    repo = repo or os.environ.get("DATA_REPO", "danhe6/medicare-aep-agent")
    cur_ptr = RELEASES / "CURRENT"
    try:
        rel = latest_release(repo)
    except Exception as e:  # offline or rate-limited: keep serving what we have
        if cur_ptr.exists():
            print(f"datasync: could not check GitHub ({e}); keeping {cur_ptr.read_text().strip()}")
            return cur_ptr.read_text().strip()
        raise
    if rel is None:
        raise RuntimeError(f"No '{PREFIX}*' releases found in {repo}")
    rid = rel["tag_name"][len(PREFIX):]
    target = RELEASES / rid
    if not (target / "manifest.json").exists():
        tmp = RELEASES / f".{rid}.download"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        assets = {a["name"]: a for a in rel["assets"]}
        for name in FILES + OPTIONAL:
            if name not in assets:
                if name in OPTIONAL:  # app still works, but say so loudly: results differ from a full release
                    print(f"datasync: WARNING release {rid} has no {name} (negotiated prices / plan history off)")
                    continue
                raise RuntimeError(f"release {rid} is missing {name}")
            a = assets[name]
            print(f"datasync: downloading {name} ({a['size']/1e6:.1f} MB)")
            with urllib.request.urlopen(_req(a["url"], "application/octet-stream"), timeout=600) as r, \
                    open(tmp / name, "wb") as f:
                shutil.copyfileobj(r, f)
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
    if not cur_ptr.exists() or cur_ptr.read_text().strip() != rid:
        t = RELEASES / "CURRENT.tmp"
        t.write_text(rid)
        t.replace(cur_ptr)
        print(f"datasync: CURRENT -> {rid}")
    return rid


if __name__ == "__main__":
    print(ensure_current())
