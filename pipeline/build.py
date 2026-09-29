"""Build a versioned, national data release from the latest CMS Part D public files.

    python pipeline/build.py                 # latest monthly (coverage) + latest quarterly (prices)
    python pipeline/build.py --list          # show what CMS has published
    python pipeline/build.py --no-promote    # build + validate, but don't switch the app to it

Layout:
  data/raw/spuf/<zip>                    immutable downloads (gitignored)
  data/raw/extracted/<zip-stem>/*.txt    extracted tables
  data/releases/<release_id>/*.parquet   one self-contained release + manifest.json
  data/releases/CURRENT                  pointer to the release the engine reads (atomic switch)

Coverage (formulary, cost sharing, plans) comes from the newest MONTHLY file; negotiated prices come
from the newest QUARTERLY file (monthly files have no prices). The manifest records both dates and
plan years so the agent can disclose "data as of".
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DOWNLOADS = RAW / "spuf"
EXTRACTED = RAW / "extracted"
RELEASES = ROOT / "data" / "releases"
CATALOG = "https://data.cms.gov/data.json"
DATASETS = {
    "monthly": "monthly prescription drug plan formulary and pharmacy network information",
    "quarterly": "quarterly prescription drug plan formulary, pharmacy network, and pricing information",
}
SKIP = ("pharmacy network", "excluded", "indication")
TABLE_KEYWORDS = [("insulin", "insulin_cost"), ("plan information", "plan_info"), ("geographic", "geo"),
                  ("basic drugs formulary", "formulary"), ("beneficiary cost", "bene_cost"), ("pricing", "pricing")]
LANDSCAPE_BY_YEAR = {  # MA/PDP Landscape per plan year; the release uses the one matching its formulary year
    "2026": "https://www.cms.gov/files/zip/cy2026-landscape-202609.zip",
    "2027": "https://www.cms.gov/files/zip/cy2027-landscape-202609.zip",
}
LANDSCAPE_URL = LANDSCAPE_BY_YEAR["2026"]
def landscape_tag(url: str = None) -> str:
    m = re.findall(r"(20\d{4})", (url or LANDSCAPE_URL).rsplit("/", 1)[-1])
    return m[-1] if m else "x"


NEED = {"monthly": ["plan_info", "geo", "formulary", "bene_cost", "insulin_cost"], "quarterly": ["pricing"]}


# ---------------------------------------------------------------- catalog / download / extract
def latest(kind: str, cat: dict | None = None) -> list[dict]:
    if cat is None:
        with urllib.request.urlopen(CATALOG, timeout=120) as r:
            cat = json.load(r)
    out = []
    for ds in cat.get("dataset", []):
        if DATASETS[kind] in ds.get("title", "").lower():
            for d in ds.get("distribution", []):
                url = d.get("downloadURL") or d.get("accessURL") or ""
                if url.lower().endswith(".zip"):
                    out.append({"kind": kind, "title": d.get("title", ""), "url": url,
                                "release": release_date(url) or d.get("modified", "")[:10].replace("-", "")})
    return sorted(out, key=lambda d: d["release"], reverse=True)


def release_date(url: str) -> str | None:
    m = re.findall(r"(20\d{6})", url.rsplit("/", 1)[-1])
    return m[-1] if m else None


def download(url: str) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    dest = DOWNLOADS / url.rsplit("/", 1)[-1]
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name}")
        return dest
    print(f"  downloading {url}")
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=900) as r, open(tmp, "wb") as f:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done/1e6:,.0f} / {total/1e6:,.0f} MB", end="", flush=True)
    print()
    tmp.replace(dest)
    return dest


def table_for(name: str) -> str | None:
    n = name.lower().replace("_", " ")
    if any(k in n for k in SKIP):
        return None
    for kw, t in TABLE_KEYWORDS:
        if kw in n:
            return t
    return None


def extract(zpath: Path, wanted: list[str]) -> dict[str, Path]:
    outdir = EXTRACTED / zpath.stem
    outdir.mkdir(parents=True, exist_ok=True)
    found = {t: outdir / f"{t}.txt" for t in wanted if (outdir / f"{t}.txt").exists()}
    if len(found) == len(wanted):
        print(f"  already extracted: {outdir.name}")
        return found

    def walk(zf: zipfile.ZipFile) -> None:
        for info in zf.infolist():
            low = info.filename.lower().replace("_", " ")
            if any(k in low for k in SKIP):
                continue
            if low.endswith(".zip"):
                with zf.open(info) as inner:
                    walk(zipfile.ZipFile(io.BytesIO(inner.read())))
            elif low.endswith((".txt", ".csv")):
                t = table_for(Path(info.filename).stem)
                if t in wanted and t not in found:
                    out = outdir / f"{t}.txt"
                    with zf.open(info) as src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found[t] = out
                    print(f"  extracted {info.filename} -> {out.relative_to(ROOT)}")

    walk(zipfile.ZipFile(zpath))
    missing = set(wanted) - set(found)
    if missing:
        raise SystemExit(f"{zpath.name} is missing tables: {missing}")
    return found


# ---------------------------------------------------------------- build / validate / promote
def to_parquet(con, src: Path, dest: Path) -> int:
    opts = "delim='|', header=true, all_varchar=true, normalize_names=true"
    try:
        con.execute(f"COPY (SELECT * FROM read_csv('{src}', {opts}, encoding='latin-1')) "
                    f"TO '{dest}' (FORMAT parquet, COMPRESSION zstd)")
    except Exception:  # older DuckDB without encoding option
        con.execute(f"COPY (SELECT * FROM read_csv('{src}', {opts}, ignore_errors=true)) "
                    f"TO '{dest}' (FORMAT parquet, COMPRESSION zstd)")
    return con.execute(f"SELECT count(*) FROM read_parquet('{dest}')").fetchone()[0]


def landscape(url: str, dest_dir: Path, con) -> int:
    """MA/PDP Landscape (annual, refreshed in-year): MOOP, star ratings, Part C/D premiums per plan x county."""
    z = DOWNLOADS / url.rsplit("/", 1)[-1]
    if not z.exists():
        print(f"  downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r:
            z.write_bytes(r.read())
    zf = zipfile.ZipFile(z)
    member = max((i for i in zf.infolist() if i.filename.lower().endswith(".csv")), key=lambda i: i.file_size)
    csv = EXTRACTED / z.stem / "landscape.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    if not csv.exists():
        csv.write_bytes(zf.read(member))

    def money(c: str) -> str:  # "$1,234.00 " / "($3.00)" -> double
        return (f"try_cast(replace(replace(replace(replace(trim({c}), '$', ''), ',', ''), '(', '-'), ')', '') AS DOUBLE)")

    con.execute(f"""
        COPY (
          SELECT contract_year, state_territory_name AS state, county_name AS county,
                 contract_id, plan_id, lpad(trim(segment_id), 3, '0') AS segment_id,
                 parent_organization_name, organization_marketing_name, plan_type, snp_type,
                 chronic_or_disabling_condition_snp_csnp_condition_type AS csnp_condition,
                 {money('innetwork_maximum_outofpocket_moop_amount')} AS moop,
                 {money('part_c_premium')} AS part_c_premium,
                 {money('part_d_total_premium')} AS part_d_premium,
                 {money('monthly_consolidated_premium_part_c_d')} AS total_monthly_premium,
                 try_cast(overall_star_rating AS DOUBLE) AS star_overall,
                 try_cast(part_c_summary_star_rating AS DOUBLE) AS star_part_c,
                 try_cast(part_d_summary_star_rating AS DOUBLE) AS star_part_d
          FROM read_csv_auto('{csv}', normalize_names=true, all_varchar=true, ignore_errors=true)
        ) TO '{dest_dir / "landscape.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    return con.execute(f"SELECT count(*) FROM read_parquet('{dest_dir / 'landscape.parquet'}')").fetchone()[0]


def validate(rel: Path, manifest: dict) -> list[str]:
    """Return a list of problems; empty list means the release is safe to promote."""
    problems = []
    rc = manifest["row_counts"]
    minimums = {"landscape": 50_000, "plan_info": 5_000, "geo": 3_000, "formulary": 500_000, "bene_cost": 50_000, "pricing": 1_000_000}
    for t, n in minimums.items():
        if rc.get(t, 0) < n:
            problems.append(f"{t} has only {rc.get(t, 0):,} rows (expected >= {n:,})")
    cur = RELEASES / "CURRENT"
    if cur.exists():
        prev_path = RELEASES / cur.read_text().strip() / "manifest.json"
        if prev_path.exists():
            prev = json.loads(prev_path.read_text())
            for t, n in rc.items():
                p = prev["row_counts"].get(t)
                if p and n < 0.7 * p and prev.get("benefit_year") == manifest.get("benefit_year"):
                    problems.append(f"{t} dropped from {p:,} to {n:,} rows vs {prev['release_id']}")
    return problems


def build(monthly: dict, quarterly: dict, promote: bool) -> Path:
    import duckdb

    print(f"\n[monthly]   {monthly['release']}  {monthly['url']}")
    m_files = extract(download(monthly["url"]), NEED["monthly"])
    print(f"[quarterly] {quarterly['release']}  {quarterly['url']}")
    q_files = extract(download(quarterly["url"]), NEED["quarterly"])

    release_id = f"m{monthly['release']}_q{quarterly['release']}"
    rel = RELEASES / release_id
    tmp = RELEASES / f".{release_id}.building"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    con = duckdb.connect()
    counts = {}
    for t, src in {**m_files, **q_files}.items():
        print(f"  parquet: {t}")
        counts[t] = to_parquet(con, src, tmp / f"{t}.parquet")
    years = [r[0] for r in con.execute(
        f"SELECT DISTINCT contract_year FROM read_parquet('{tmp / 'formulary.parquet'}') ORDER BY 1").fetchall()]
    ls_url = LANDSCAPE_BY_YEAR.get(str(years[-1]) if years else "", LANDSCAPE_URL)
    print(f"  parquet: landscape ({ls_url.rsplit('/', 1)[-1]})")
    counts["landscape"] = landscape(ls_url, tmp, con)
    try:                                   # plan history tables built by pipeline/history.py (optional)
        from history import copy_into
        print("  history:", copy_into(tmp))
    except Exception as e:
        print("  history: skipped -", e)
    try:                                   # IRA negotiated prices (optional: a failure never blocks a release)
        from mfp import build as build_mfp
        counts["mfp"] = build_mfp(tmp, con)
    except Exception as e:
        print("  mfp: skipped -", e)
    price_year = re.findall(r"SPUF_(20\d\d)", quarterly["url"]) or [quarterly["release"][:4]]
    manifest = {
        "release_id": release_id, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "benefit_year": years[-1] if years else None, "benefit_years": years, "price_year": price_year[0],
        "sources": {"monthly": monthly, "quarterly": quarterly,
                    "landscape": {"url": ls_url, "release": landscape_tag(ls_url)}}, "row_counts": counts,
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1))
    problems = validate(tmp, manifest)
    if problems:
        print("\nVALIDATION FAILED - release NOT promoted:\n  " + "\n  ".join(problems))
        sys.exit(1)
    shutil.rmtree(rel, ignore_errors=True)
    tmp.rename(rel)
    print(f"\nBuilt {rel.relative_to(ROOT)}  benefit_year={manifest['benefit_year']} price_year={manifest['price_year']}")
    print("  rows:", {k: f"{v:,}" for k, v in counts.items()})
    if promote:
        ptr = RELEASES / "CURRENT.tmp"
        ptr.write_text(release_id)
        ptr.replace(RELEASES / "CURRENT")
        print(f"Promoted: CURRENT -> {release_id}")
    return rel


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--plan", action="store_true", help="print the release that would be built (JSON) and exit")
    ap.add_argument("--monthly-url")
    ap.add_argument("--quarterly-url")
    a = ap.parse_args()
    if not a.plan:
        print("Reading CMS catalog ...")
    with urllib.request.urlopen(CATALOG, timeout=120) as r:
        cat = json.load(r)
    mon, qtr = latest("monthly", cat), latest("quarterly", cat)
    if a.list:
        for d in mon[:4] + qtr[:4]:
            print(f"  {d['kind']:9} {d['release']}  {d['url']}")
        return
    m = {"kind": "monthly", "url": a.monthly_url, "release": release_date(a.monthly_url)} if a.monthly_url else mon[0]
    q = {"kind": "quarterly", "url": a.quarterly_url, "release": release_date(a.quarterly_url)} if a.quarterly_url else qtr[0]
    if a.plan:
        print(json.dumps({"release_id": f"m{m['release']}_q{q['release']}", "monthly": m, "quarterly": q}))
        return
    build(m, q, promote=not a.no_promote)


if __name__ == "__main__":
    main()
