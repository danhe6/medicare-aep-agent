"""Publish a built data release as a GitHub Release (tag: data-<release_id>).

    python pipeline/publish.py                      # publish data/releases/CURRENT
    python pipeline/publish.py --release m20260916_q20260701
    python pipeline/publish.py --exists m2026..._q2026...   # exit 0 if already published, 1 if not

Requires the GitHub CLI (`gh`) authenticated (in GitHub Actions: GH_TOKEN=${{ github.token }}).
The newest release whose tag starts with "data-" is what the app downloads (engine/datasync.py).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "data" / "releases"
PREFIX = "data-"


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def exists(release_id: str) -> bool:
    return gh("release", "view", PREFIX + release_id, check=False).returncode == 0


def publish(release_id: str) -> None:
    rel = RELEASES / release_id
    m = json.loads((rel / "manifest.json").read_text())
    if exists(release_id):
        print(f"Already published: {PREFIX}{release_id}")
        return
    rc = "\n".join(f"| {t} | {n:,} |" for t, n in m["row_counts"].items())
    notes = (f"Automated CMS Part D data release.\n\n"
             f"- Coverage (monthly PUF): {m['sources']['monthly']['release']}\n"
             f"- Prices (quarterly PUF): {m['sources']['quarterly']['release']}\n"
             f"- Benefit year: {m['benefit_year']} | price year: {m['price_year']}\n"
             f"- Built: {m['built_at']}\n\n| table | rows |\n| --- | --- |\n{rc}\n")
    files = sorted(str(p) for p in rel.iterdir() if p.suffix in (".parquet", ".json"))
    gh("release", "create", PREFIX + release_id, *files, "--title", f"Data {release_id}", "--notes", notes)
    print(f"Published {PREFIX}{release_id} ({len(files)} files)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release")
    ap.add_argument("--exists")
    a = ap.parse_args()
    if a.exists:
        sys.exit(0 if exists(a.exists) else 1)
    publish(a.release or (RELEASES / "CURRENT").read_text().strip())


if __name__ == "__main__":
    main()
