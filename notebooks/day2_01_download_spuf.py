"""Day 2, step 1: download the CMS Part D public use file and load Miami-Dade plans into DuckDB.

Run from the repo root:
    python3 -m pip install --user duckdb
    python3 notebooks/day2_01_download_spuf.py            # auto-find latest quarterly file
    python3 notebooks/day2_01_download_spuf.py --list     # just list available files
    python3 notebooks/day2_01_download_spuf.py --url URL  # use a specific zip

Downloads ~1-2 GB once into data/raw/spuf/ (gitignored). The huge pharmacy-network
table is skipped. Output: data/processed/partd.duckdb
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "spuf"
DB = ROOT / "data" / "processed" / "partd.duckdb"
CATALOG = "https://data.cms.gov/data.json"
DATASET = "quarterly prescription drug plan formulary, pharmacy network, and pricing information"

# inner file keyword -> table name (checked in order)
TABLES = [
    ("pharmacy network", None),          # skip: very large, not needed for the spike
    ("excluded", None),
    ("indication", None),
    ("insulin", "insulin_cost"),
    ("plan information", "plan_info"),
    ("geographic", "geo"),
    ("basic drugs formulary", "formulary"),
    ("beneficiary cost", "bene_cost"),
    ("pricing", "pricing"),
]


def table_for(name: str) -> str | None:
    n = name.lower().replace("_", " ")
    for kw, table in TABLES:
        if kw in n:
            return table
    return None


def list_distributions() -> list[dict]:
    print("Reading CMS catalog ...")
    with urllib.request.urlopen(CATALOG, timeout=120) as r:
        cat = json.load(r)
    out = []
    for ds in cat.get("dataset", []):
        if DATASET in ds.get("title", "").lower():
            for d in ds.get("distribution", []):
                url = d.get("downloadURL") or d.get("accessURL") or ""
                if url.lower().endswith(".zip"):
                    out.append({"title": d.get("title", ""), "url": url, "modified": d.get("modified", "")})
    out.sort(key=lambda d: (d["modified"], d["title"]), reverse=True)
    return out


def download(url: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / url.rsplit("/", 1)[-1]
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Already downloaded: {dest.name}")
        return dest
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=600) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done/1e6:,.0f} / {total/1e6:,.0f} MB", end="", flush=True)
    print()
    return dest


def extract(zpath: Path) -> dict[str, Path]:
    """Walk the (possibly nested) zip; extract the tables we need as .txt files."""
    found: dict[str, Path] = {}

    def walk(zf: zipfile.ZipFile) -> None:
        for info in zf.infolist():
            name = info.filename
            if name.lower().endswith(".zip"):
                low = name.lower().replace("_", " ")
                if any(k in low for k, t in TABLES if t is None):
                    continue  # skip huge / unneeded nested archives
                with zf.open(info) as inner:
                    walk(zipfile.ZipFile(io.BytesIO(inner.read())))
            elif name.lower().endswith((".txt", ".csv")):
                table = table_for(Path(name).stem)
                if table and table not in found:
                    out = RAW / f"{table}.txt"
                    with zf.open(info) as src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found[table] = out
                    print(f"  extracted {name} -> {out.name}")

    walk(zipfile.ZipFile(zpath))
    return found


def load(files: dict[str, Path]) -> None:
    import duckdb

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))

    def src(t: str) -> str:
        return (f"read_csv('{files[t]}', delim='|', header=true, all_varchar=true, "
                f"ignore_errors=true, normalize_names=true)")

    for t in ("plan_info", "geo", "formulary", "bene_cost", "insulin_cost"):
        if t in files:
            con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {src(t)}")

    print("\nColumns (send these to Claude if the next step errors):")
    for t in ("plan_info", "geo", "formulary", "bene_cost", "pricing"):
        if t in files:
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src(t)} LIMIT 0").fetchall()]
            print(f"  {t}: {cols}")

    # Miami-Dade plans (county name match on the geographic locator)
    con.execute("""
        CREATE OR REPLACE TABLE miami_plans AS
        WITH g AS (
            SELECT county_code, trim(pdp_region_code) AS pdp_region_code FROM geo
            WHERE lower(statename) LIKE 'florida%' AND lower(county) LIKE '%dade%'
        )
        SELECT DISTINCT p.*
        FROM plan_info p, g
        WHERE (trim(p.county_code) = g.county_code                       -- MA-PD plans (county level)
               OR (p.contract_id LIKE 'S%'                               -- stand-alone PDPs (region level)
                   AND trim(p.pdp_region_code) = g.pdp_region_code))
          AND coalesce(p.plan_suppressed_yn, 'N') <> 'Y'
    """)
    n = con.execute("SELECT count(*) FROM miami_plans").fetchone()[0]
    print(f"\nMiami-Dade plans: {n}")
    print("  by type:", con.execute("SELECT left(contract_id,1) t, count(*) FROM miami_plans GROUP BY 1 ORDER BY 1").fetchall())

    # Pricing is large: keep only Miami-Dade plans
    if "pricing" in files:
        con.execute(f"""
            CREATE OR REPLACE TABLE pricing AS
            SELECT pr.* FROM {src('pricing')} pr
            JOIN (SELECT DISTINCT contract_id, plan_id FROM miami_plans) m
              ON pr.contract_id = m.contract_id AND pr.plan_id = m.plan_id
        """)
        print("pricing rows kept:", con.execute("SELECT count(*) FROM pricing").fetchone()[0])
    print("\nSample (cheapest premiums):")
    for row in con.execute("""
        SELECT contract_id, plan_id, segment_id, plan_name, premium, deductible
        FROM miami_plans ORDER BY try_cast(premium AS DOUBLE) LIMIT 10
    """).fetchall():
        print("  ", row)
    con.close()
    print(f"\nSaved {DB}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--url")
    a = ap.parse_args()
    if a.url:
        url = a.url
    else:
        dists = list_distributions()
        if not dists:
            sys.exit("No zip found in the CMS catalog. Open data.cms.gov, search the dataset, copy the zip link, "
                     "and re-run with --url.")
        for d in dists[:8]:
            print(f"  {d['modified'][:10]}  {d['title']}\n      {d['url']}")
        if a.list:
            return
        url = dists[0]["url"]
        print(f"\nUsing latest: {url}")
    wanted = ("plan_info", "geo", "formulary", "bene_cost", "pricing", "insulin_cost")
    cached = {t: RAW / f"{t}.txt" for t in wanted if (RAW / f"{t}.txt").exists()}
    if len(cached) == len(wanted):
        print("Using already-extracted files in data/raw/spuf/")
        files = cached
    else:
        files = extract(download(url))
    missing = {"plan_info", "geo", "formulary", "bene_cost", "pricing"} - set(files)
    if missing:
        print("WARNING: tables not found in zip:", missing)
    load(files)


if __name__ == "__main__":
    main()
