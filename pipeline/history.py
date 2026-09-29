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


def _years_in(segment: str) -> set[str]:
    import re
    return set(re.findall(r"20[0-3]\d", segment))


def walk_csvs(zf: zipfile.ZipFile, prefix: str = "", wanted: tuple = ()):
    """Yield (path, size, reader) for every CSV, descending into nested zips (the archive holds one zip per year).
    With `wanted`, only enter zips/files whose own name mentions a wanted year (or no year at all)."""
    for info in zf.infolist():
        name = prefix + info.filename
        last = info.filename.rstrip("/").rsplit("/", 1)[-1]
        ys = _years_in(last)
        if wanted and ys and not (ys & set(wanted)):
            continue
        if info.filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                yield from walk_csvs(inner, name + "/", wanted)
        elif info.filename.lower().endswith(".csv"):
            yield name, info.file_size, lambda i=info: zf.read(i)


def inspect_landscape() -> None:
    for key, url in LANDSCAPE.items():
        z = fetch(url)
        print(f"\n##### {key}: {z.name} ({z.stat().st_size / 1e6:,.0f} MB)")
        with zipfile.ZipFile(z) as zf:
            for name, size, read in walk_csvs(zf, wanted=YEARS_WANTED if key.startswith("archive") else ()):
                raw = read()[:20000].decode("latin-1", errors="replace")
                raw = raw[: raw.rfind("\n")] if "\n" in raw else raw      # don't cut a row in half
                try:
                    rows = list(csv.reader(io.StringIO(raw, newline="")))
                except csv.Error:
                    rows = [line.split(",") for line in raw.splitlines()[:4]]
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


LANDSCAPE_YEARS = {  # one unified format from CY2025 on
    "2025": ("archive_2006_2025", "CY2025_Landscape_202506.1.csv"),
    "2026": ("2026", "CY2026_Landscape_202609.csv"),
    "2027": ("2027", "CY2027_Landscape_202609.csv"),
}


def _extract_landscape_csv(key: str, csv_name: str) -> Path:
    out = EXTRACTED / "landscape_history" / csv_name
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(fetch(LANDSCAPE[key])) as zf:
        for name, _size, read in walk_csvs(zf, wanted=("2025", "2026", "2027")):
            if name.endswith(csv_name):
                out.write_bytes(read())
                return out
    raise FileNotFoundError(csv_name)


def landscape_history() -> None:
    """One row per plan and year: premium, Part D premium, in-network MOOP, overall stars (2025-2027)."""
    import duckdb
    con = duckdb.connect()
    parts = []
    for year, (key, csv_name) in LANDSCAPE_YEARS.items():
        src = _extract_landscape_csv(key, csv_name)
        con.execute(f"""CREATE OR REPLACE TABLE raw_{year} AS SELECT * FROM read_csv_auto('{src}',
                        normalize_names=true, all_varchar=true, ignore_errors=true)""")
        cols = [r[0] for r in con.execute(f"DESCRIBE raw_{year}").fetchall()]
        pick = lambda *keys, avoid=(): next((c for c in cols if all(k in c for k in keys)  # noqa: E731
                                             and not any(a in c for a in avoid)), None)
        m = {"premium": pick("monthly_consolidated_premium"), "part_d_premium": pick("part_d_total_premium"),
             "moop": pick("moop", avoid=("out_of_network", "combined", "outofnetwork")),
             "star": pick("overall_star"), "plan_name": pick("plan_name"), "org": pick("organization_marketing_name"),
             "snp": pick("snp_type"), "plan_type": pick("plan_type")}
        print(f"{year}: columns used {m}")
        money = lambda c: (f"try_cast(replace(replace(replace(replace(trim({c}), '$', ''), ',', ''), '(', '-'), ')', '') AS DOUBLE)"  # noqa: E731
                           if c else "NULL::DOUBLE")
        txt = lambda c: c if c else "NULL::VARCHAR"  # noqa: E731
        parts.append(f"""SELECT DISTINCT ON (contract_id, plan_id, segment_id)
               {year} AS year, contract_id, plan_id, lpad(trim(segment_id), 3, '0') AS segment_id,
               {txt(m['plan_name'])} AS plan_name, {txt(m['org'])} AS org, {txt(m['plan_type'])} AS plan_type,
               {txt(m['snp'])} AS snp_type,
               {money(m['premium'])} AS premium, {money(m['part_d_premium'])} AS part_d_premium,
               {money(m['moop'])} AS moop, try_cast({txt(m['star'])} AS DOUBLE) AS star
             FROM raw_{year}""")
    HIST.mkdir(parents=True, exist_ok=True)
    out = HIST / "plan_years.parquet"
    con.execute(f"COPY ({' UNION ALL '.join(parts)}) TO '{out}' (FORMAT parquet, COMPRESSION zstd)")
    print(con.execute(f"SELECT year, count(*), count(moop), count(star), round(median(premium), 2) "
                      f"FROM read_parquet('{out}') GROUP BY 1 ORDER BY 1").fetchall())
    print("\nSample 2026 -> 2027 changes (plans in both years):")
    rows = con.execute(f"""
        SELECT a.contract_id || '-' || a.plan_id AS plan, a.plan_name, a.premium, b.premium, a.moop, b.moop, a.star, b.star
        FROM read_parquet('{out}') a JOIN read_parquet('{out}') b USING (contract_id, plan_id, segment_id)
        WHERE a.year = 2026 AND b.year = 2027 AND a.contract_id LIKE 'H1019%' LIMIT 8""").fetchall()
    for r in rows:
        print("  ", r)
    n = con.execute(f"""SELECT count(*) FROM read_parquet('{out}') a JOIN read_parquet('{out}') b
                        USING (contract_id, plan_id, segment_id) WHERE a.year = 2026 AND b.year = 2027""").fetchone()[0]
    n26 = con.execute(f"SELECT count(*) FROM read_parquet('{out}') WHERE year = 2026").fetchone()[0]
    print(f"\n2026 plans that continue into 2027 under the same ID: {n:,} of {n26:,}")


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


RELEASE_NAMES = {'plan_years.parquet': 'hist_plan_years.parquet', 'formulary_changes_2025_2026.parquet': 'hist_formulary_changes.parquet', 'plan_map_2025_2026.parquet': 'hist_plan_map.parquet', 'contract_stability_2025_2026.parquet': 'hist_contract_stability.parquet'}


def copy_into(release_dir: Path) -> list[str]:
    """Copy the built history tables into a data release (they then ship with it)."""
    done = []
    for src, dst in RELEASE_NAMES.items():
        if (HIST / src).exists():
            shutil.copy2(HIST / src, release_dir / dst)
            done.append(dst)
    return done


if __name__ == "__main__":
    if "--into-current" in sys.argv:
        sys.path.insert(0, str(ROOT / "src"))
        from engine import data
        print("copied:", copy_into(data.current_release()))
        sys.exit()
    if "--landscape-history" in sys.argv:
        landscape_history()
        sys.exit()
    if "--stability" in sys.argv:
        stability()
        sys.exit()
    if "--inspect-landscape" in sys.argv:
        inspect_landscape()
    elif "--formulary" in sys.argv:
        formulary_history()
    else:
        print(__doc__)
