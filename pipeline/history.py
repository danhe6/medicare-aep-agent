"""Plan history: how plans behaved in past years (premiums, out-of-pocket max, stars, formulary changes).

    PYTHONPATH=src python pipeline/history.py --inspect-landscape   # step 1: download + show old file formats
    PYTHONPATH=src python pipeline/history.py --formulary           # step 2: Jan 2025 + Jan 2026 formularies

Outputs go to data/history/ (gitignored with data/). Big CMS zips are deleted after extraction.
This is PAST behavior, shown as "the record", never as a prediction.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CATALOG, DOWNLOADS, EXTRACTED, NEED, download, extract, latest, to_parquet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "history"
LANDSCAPE = {
    "archive_2006_2025": "https://www.cms.gov/files/zip/cy2006-cy2025-landscape-files.zip",
    "2026": "https://www.cms.gov/files/zip/cy2026-landscape-202609.zip",
    "2027": "https://www.cms.gov/files/zip/cy2027-landscape-202609.zip",
}
YEARS_WANTED = ("2022", "2023", "2024", "2025")      # from the archive
FORMULARY_SNAPSHOTS = ("2025", "2026")                # January monthly file of each year


def fetch(url: str) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    z = DOWNLOADS / url.rsplit("/", 1)[-1]
    if not z.exists():
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1200) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f)
    return z


def walk_csvs(zf: zipfile.ZipFile, prefix: str = ""):
    """Yield (path, bytes) for every CSV, descending into nested zips (the archive holds one zip per year)."""
    for info in zf.infolist():
        name = prefix + info.filename
        if info.filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                yield from walk_csvs(inner, name + "/")
        elif info.filename.lower().endswith(".csv"):
            yield name, info.file_size, lambda i=info: zf.read(i)


def inspect_landscape() -> None:
    for key, url in LANDSCAPE.items():
        z = fetch(url)
        print(f"\n##### {key}: {z.name} ({z.stat().st_size / 1e6:,.0f} MB)")
        with zipfile.ZipFile(z) as zf:
            for name, size, read in walk_csvs(zf):
                if key.startswith("archive") and not any(y in name for y in YEARS_WANTED):
                    continue
                raw = read()[:20000].decode("latin-1", errors="replace")
                rows = list(csv.reader(io.StringIO(raw)))
                # header may not be the first line in old files: show the first 4 rows
                print(f"\n=== {name}  ({size / 1e6:,.1f} MB)")
                for r in rows[:4]:
                    print("   ", r[:40])


def formulary_history() -> None:
    import duckdb
    with urllib.request.urlopen(CATALOG, timeout=120) as r:
        cat = json.load(r)
    monthly = latest("monthly", cat)
    HIST.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for year in FORMULARY_SNAPSHOTS:
        cands = sorted((d for d in monthly if str(d["release"]).startswith(year)), key=lambda d: str(d["release"]))
        if not cands:
            print(f"{year}: no monthly release in the catalog")
            continue
        d = cands[0]                                   # earliest release of the year = that year's formularies
        out = HIST / f"formulary_{year}.parquet"
        if out.exists():
            print(f"{year}: already built ({out.name})")
            continue
        print(f"\n{year}: monthly release {d['release']}")
        zpath = download(d["url"])
        files = extract(zpath, ["plan_info", "formulary"])
        n_f = to_parquet(con, files["formulary"], out)
        n_p = to_parquet(con, files["plan_info"], HIST / f"plan_info_{year}.parquet")
        print(f"  formulary rows {n_f:,}, plan_info rows {n_p:,}")
        zpath.unlink(missing_ok=True)                  # free the ~2 GB download
        shutil.rmtree(EXTRACTED / zpath.stem, ignore_errors=True)
    print("\nDone:", sorted(p.name for p in HIST.glob("*.parquet")))


def stability() -> None:
    """Year-over-year formulary changes per plan (2025 -> 2026): which drugs each plan removed, moved to a higher
    tier, or put behind prior authorization / step therapy. Plans are matched by contract + plan + segment."""
    import duckdb
    con = duckdb.connect()
    f = lambda n: HIST / n  # noqa: E731
    con.execute(f"""
      CREATE TABLE plan_map AS
      SELECT a.contract_id, a.plan_id, lpad(trim(a.segment_id), 3, '0') AS segment_id,
             a.formulary_id AS f_old, b.formulary_id AS f_new
      FROM (SELECT DISTINCT contract_id, plan_id, segment_id, formulary_id FROM read_parquet('{f("plan_info_2025.parquet")}')) a
      JOIN (SELECT DISTINCT contract_id, plan_id, segment_id, formulary_id FROM read_parquet('{f("plan_info_2026.parquet")}')) b
        USING (contract_id, plan_id, segment_id)""")
    for y in ("2025", "2026"):
        con.execute(f"""
          CREATE TABLE fx_{y} AS
          SELECT formulary_id, rxcui, min(try_cast(tier_level_value AS INT)) AS tier,
                 bool_or(upper(prior_authorization_yn) = 'Y') AS pa, bool_or(upper(step_therapy_yn) = 'Y') AS st
          FROM read_parquet('{f(f"formulary_{y}.parquet")}')
          WHERE formulary_id IN (SELECT {'f_old' if y == '2025' else 'f_new'} FROM plan_map)
          GROUP BY 1, 2""")
    # drugs that still exist on SOME 2026 formulary: only those can be a plan's own decision to drop
    con.execute(f"""CREATE TABLE universe_2026 AS
                    SELECT DISTINCT rxcui FROM read_parquet('{f("formulary_2026.parquet")}')""")
    con.execute("""
      CREATE TABLE changes AS
      WITH pairs AS (SELECT DISTINCT f_old, f_new FROM plan_map)
      SELECT p.f_old, p.f_new, o.rxcui, o.tier AS tier_old, n.tier AS tier_new,
             CASE WHEN n.rxcui IS NULL AND o.rxcui NOT IN (SELECT rxcui FROM universe_2026) THEN 'gone_everywhere'
                  WHEN n.rxcui IS NULL THEN 'removed'
                  WHEN n.tier > o.tier THEN 'tier_up'
                  WHEN n.pa AND NOT o.pa THEN 'pa_added'
                  WHEN n.st AND NOT o.st THEN 'st_added' END AS change
      FROM pairs p JOIN fx_2025 o ON o.formulary_id = p.f_old
      LEFT JOIN fx_2026 n ON n.formulary_id = p.f_new AND n.rxcui = o.rxcui""")
    con.execute(f"COPY (SELECT * FROM changes WHERE change IS NOT NULL) TO '{f('formulary_changes_2025_2026.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    con.execute(f"COPY plan_map TO '{f('plan_map_2025_2026.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    con.execute(f"""
      COPY (
        SELECT m.contract_id, count(DISTINCT m.plan_id) AS plans,
               count(*) AS drug_slots,
               round(100.0 * count(*) FILTER (WHERE c.change = 'removed') / count(*), 2) AS pct_removed,
               round(100.0 * count(*) FILTER (WHERE c.change IN ('removed', 'pa_added', 'st_added')) / count(*), 2) AS pct_worse,
               round(100.0 * count(*) FILTER (WHERE c.change = 'tier_up') / count(*), 2) AS pct_tier_up_info
        FROM plan_map m JOIN changes c ON c.f_old = m.f_old AND c.f_new = m.f_new
        WHERE c.change IS DISTINCT FROM 'gone_everywhere'
        GROUP BY 1) TO '{f('contract_stability_2025_2026.parquet')}' (FORMAT parquet, COMPRESSION zstd)""")
    n_map = con.execute("SELECT count(*) FROM plan_map").fetchone()[0]
    n_old = con.execute(f"SELECT count(DISTINCT (contract_id, plan_id, segment_id)) FROM read_parquet('{f('plan_info_2025.parquet')}')").fetchone()[0]
    print(f"plans matched 2025 -> 2026: {n_map:,} of {n_old:,} (2025 plans)")
    print("\nchanges by type:")
    for row in con.execute("SELECT coalesce(change, 'unchanged'), count(*) FROM changes GROUP BY 1 ORDER BY 2 DESC").fetchall():
        print(f"  {row[0]:10} {row[1]:>12,}")
    print("\ncontracts: (contract, plans, drug slots, % removed, % worse = removed+PA+ST added, % tier-number up [info])")
    rows = con.execute(f"SELECT * FROM read_parquet('{f('contract_stability_2025_2026.parquet')}') ORDER BY pct_worse").fetchall()
    for r in rows[:5] + [("...",)] + rows[-5:]:
        print("  ", r)
    print(f"\n{len(rows)} contracts;",
          "median pct_worse", con.execute(f"SELECT median(pct_worse) FROM read_parquet('{f('contract_stability_2025_2026.parquet')}')").fetchone()[0])


if __name__ == "__main__":
    if "--stability" in sys.argv:
        stability()
        sys.exit()
    if "--inspect-landscape" in sys.argv:
        inspect_landscape()
    elif "--formulary" in sys.argv:
        formulary_history()
    else:
        print(__doc__)
