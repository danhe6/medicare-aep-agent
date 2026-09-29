"""How far back do CMS Part D public files go, and how big are they? (feasibility check for plan-stability history)

    python pipeline/history_check.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CATALOG, latest  # noqa: E402


def size_mb(url: str) -> str:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "medicare-aep-agent"})
        with urllib.request.urlopen(req, timeout=30) as r:
            n = int(r.headers.get("Content-Length") or 0)
        return f"{n / 1e6:,.0f} MB" if n else "?"
    except Exception as e:
        return f"? ({type(e).__name__})"


with urllib.request.urlopen(CATALOG, timeout=120) as r:
    cat = json.load(r)
for kind in ("monthly", "quarterly"):
    rows = latest(kind, cat)
    print(f"\n{kind}: {len(rows)} releases in the catalog")
    by_year = {}
    for d in rows:
        by_year.setdefault(str(d["release"])[:4], []).append(d)
    for y in sorted(by_year):
        ds = sorted(by_year[y], key=lambda d: str(d["release"]))
        print(f"  {y}: {len(ds):2} releases  e.g. {ds[0]['release']} .. {ds[-1]['release']}")
    for d in sorted(rows, key=lambda d: str(d["release"]))[:1] + rows[:1]:
        print(f"  size check {d['release']}: {size_mb(d['url'])}")
