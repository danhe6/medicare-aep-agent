"""IRA negotiated prices ("Maximum Fair Prices") from CMS: official per-unit prices by NDC-9.

    PYTHONPATH=src python pipeline/mfp.py --inspect     # download + show the file's columns (first run)
    PYTHONPATH=src python pipeline/mfp.py               # build data/processed/mfp.parquet

Source: CMS "Selected Drug List and Negotiated Prices" (Medicare Drug Price Negotiation Program).
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://www.cms.gov/files/zip/selected-drug-list-negotiated-prices-also-known-maximum-fair-prices-statutezip.zip"
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "mfp"


def download() -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / "mfp.zip"
    req = urllib.request.Request(URL, headers={"User-Agent": "medicare-aep-agent"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    return dest


def csv_tables(zpath: Path):
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if name.lower().endswith(".csv"):
                raw = z.read(name)
                text = raw.decode("utf-8-sig", errors="replace")
                yield name, list(csv.reader(io.StringIO(text)))


def inspect() -> None:
    z = download()
    with zipfile.ZipFile(z) as zz:
        print("files in zip:", zz.namelist())
    for name, rows in csv_tables(z):
        print(f"\n=== {name}: {len(rows)} rows")
        for r in rows[:8]:
            print(r)


def build(dest_dir: Path, con=None, zpath: Path | None = None) -> int:
    """Write dest_dir/mfp.parquet: one row per NDC-11 and price period (IPAY 2026 drugs have an inflation-adjusted
    row starting 2027-01-01; IPAY 2027 drugs start 2027-01-01)."""
    import duckdb
    con = con or duckdb.connect()
    zpath = zpath or download()
    name, rows = next(csv_tables(zpath))
    head = rows[0]
    col = {h: i for i, h in enumerate(head)}
    need = ["IPAY", "Selected Drug Name", "NDC-9", "NDC-11", "MFP Effective Date", "MFP End Date",
            "Single MFP per 30 DES", "NDC-9 MFP per Unit Price"]
    missing = [c for c in need if c not in col]
    if missing:
        raise RuntimeError(f"MFP file columns changed, missing: {missing}")
    out = []
    for r in rows[1:]:
        if len(r) < len(head) or not r[col["NDC-11"]].strip():
            continue
        try:
            unit = float(r[col["NDC-9 MFP per Unit Price"]])
        except ValueError:
            continue
        def iso(s):
            s = s.strip()
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}" if len(s) == 10 else None
        out.append((r[col["IPAY"]].strip(), r[col["Selected Drug Name"]].strip(), r[col["NDC-9"]].replace("-", ""),
                    r[col["NDC-11"]].replace("-", "").strip(), iso(r[col["MFP Effective Date"]]),
                    iso(r[col["MFP End Date"]]), unit, r[col["Single MFP per 30 DES"]].strip()))
    con.execute("""CREATE OR REPLACE TABLE _mfp (ipay VARCHAR, drug VARCHAR, ndc9 VARCHAR, ndc VARCHAR,
                   start_date DATE, end_date DATE, unit_price DOUBLE, mfp_30day VARCHAR)""")
    con.executemany("INSERT INTO _mfp VALUES (?, ?, ?, ?, ?, ?, ?, ?)", out)
    dest = dest_dir / "mfp.parquet"
    con.execute(f"COPY _mfp TO '{dest}' (FORMAT parquet, COMPRESSION zstd)")
    print(f"  mfp: {len(out)} rows from {name}")
    return len(out)


def check_against_pricing() -> None:
    """Sanity check: 2026 negotiated unit prices vs the plans' 2026 unit costs in the CMS pricing file (same units?)."""
    import duckdb
    sys.path.insert(0, str(ROOT / "src"))
    from engine import data
    rel = data.current_release()
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT m.drug, round(m.unit_price, 3) AS mfp_2026_unit,
               round(median(try_cast(p.unit_cost AS DOUBLE)), 3) AS plans_median_unit_2026, count(*) AS n
        FROM read_parquet('{rel / "mfp.parquet"}') m
        JOIN read_parquet('{rel / "pricing.parquet"}') p ON p.ndc = m.ndc
        WHERE m.start_date = DATE '2026-01-01' AND p.days_supply IN ('30', '030', '1')
        GROUP BY 1, 2 ORDER BY 1 LIMIT 30""").fetchall()
    print(f"\n{'drug':32} {'2026 negotiated/unit':>22} {'plans median/unit 2026':>24} {'n':>6}")
    for d, mfp, med, n in rows:
        flag = "" if med and abs(med - mfp) / mfp < 0.25 else "   <-- check units"
        print(f"{d[:32]:32} {mfp:>22} {med if med is not None else '-':>24} {n:>6}{flag}")


if __name__ == "__main__":
    if "--inspect" in sys.argv:
        inspect()
    elif "--into-current" in sys.argv:       # add mfp.parquet to the release in use (no full rebuild)
        sys.path.insert(0, str(ROOT / "src"))
        from engine import data
        build(data.current_release())
        check_against_pricing()
    else:
        print(__doc__)
