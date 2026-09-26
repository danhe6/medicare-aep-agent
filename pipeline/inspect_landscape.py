"""Download the CMS MA/PDP Landscape zip and print what's inside (columns, plan years, Miami sample).

    python pipeline/inspect_landscape.py [URL]
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.cms.gov/files/zip/cy2026-landscape-202609.zip"
dest = ROOT / "data" / "raw" / "landscape" / URL.rsplit("/", 1)[-1]
dest.parent.mkdir(parents=True, exist_ok=True)
if not dest.exists():
    print("downloading", URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())
zf = zipfile.ZipFile(dest)
for i in zf.infolist():
    print(f"  {i.file_size/1e6:8.1f} MB  {i.filename}")
csvs = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
big = max(csvs, key=lambda i: i.file_size)
out = dest.parent / Path(big.filename).name
out.write_bytes(zf.read(big))
import duckdb
con = duckdb.connect()
con.execute(f"CREATE VIEW l AS SELECT * FROM read_csv_auto('{out}', normalize_names=true, all_varchar=true, ignore_errors=true)")
cols = [r[0] for r in con.execute("DESCRIBE l").fetchall()]
print("\nCOLUMNS:", cols)
print("rows:", con.execute("SELECT count(*) FROM l").fetchone()[0])
yc = [c for c in cols if "year" in c]
if yc:
    print("years:", con.execute(f"SELECT {yc[0]}, count(*) FROM l GROUP BY 1").fetchall())
cc = [c for c in cols if "county" in c]
if cc:
    print("\nMiami-Dade sample:")
    for row in con.execute(f"SELECT * FROM l WHERE lower({cc[0]}) LIKE '%miami%' LIMIT 2").fetchall():
        print(dict(zip(cols, row)))
