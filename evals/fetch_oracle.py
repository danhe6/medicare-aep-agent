"""Collect Medicare Plan Finder's own annual drug-cost estimates as the eval "answer key".

Uses the (undocumented) JSON endpoint behind medicare.gov/plan-compare. TEST USE ONLY: the product
must never depend on it. Prices at one fixed in-network pharmacy (CVS, 650 NW 27th Ave, Miami 33125).

    python evals/fetch_oracle.py            # all personas in evals/personas/p*.json
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

EVALS = Path(__file__).resolve().parent
URL = "https://www.medicare.gov/api/v1/data/plan-compare/drugs/cost"
PHARMACY_NPI = "1174627087"  # HOLIDAY CVS LLC, 650 NW 27TH AVE, MIAMI FL 33125
YEAR = "2026"
BATCH = 8
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.medicare.gov",
    "Referer": "https://www.medicare.gov/plan-compare/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
}


def post(body: dict) -> dict:
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> None:
    plans = json.loads((EVALS / "plans_miami_nonsnp.json").read_text())
    for path in sorted((EVALS / "personas").glob("p[0-9]*.json")):
        persona = json.loads(path.read_text())
        rx = [{"ndc": d["oracle_ndc"], "frequency": "FREQUENCY_30_DAYS", "quantity": d["qty_per_30d"]}
              for d in persona["drugs"] if d.get("oracle_ndc")]
        answers = {}
        for i in range(0, len(plans), BATCH):
            chunk = plans[i:i + BATCH]
            body = {"npis": [PHARMACY_NPI], "prescriptions": rx, "lis": "LIS_NO_HELP",
                    "plans": [{"contract_id": k.split("-")[0], "plan_id": k.split("-")[1],
                               "segment_id": str(int(k.split("-")[2])), "contract_year": YEAR} for k in chunk],
                    "full_year": True, "retailOnly": True}
            try:
                res = post(body)
            except urllib.error.HTTPError as e:
                raise SystemExit(f"HTTP {e.code}: {e.read()[:300]!r}\n"
                                 "If this is 403, Plan Finder is blocking scripts; ask Claude to collect via browser.")
            for p in res.get("plans", []):
                key = f"{p['plan']['contract_id']}-{p['plan']['plan_id']}-{int(p['plan']['segment_id']):03d}"
                c = (p.get("costs") or [{}])[0]
                answers[key] = {
                    "yearly_total": c.get("estimated_yearly_total"),
                    "preferred_pharmacy": c.get("preferred"),
                    "in_network": c.get("in_network"),
                    "drugs": [{"ndc": d["ndc"], "covered": d.get("covered"), "tier": d.get("tier"),
                               "full_cost_30d": d.get("full_cost"), "yearly": d.get("estimated_yearly_total")}
                              for d in c.get("drug_costs", [])],
                    "excluded": p.get("excluded_drugs", []),
                }
            time.sleep(0.5)
        n_sent = len(rx)
        partial = sum(1 for a in answers.values() if len(a["drugs"]) != n_sent)
        out = {"persona": persona["name"], "year": YEAR, "pharmacy_npi": PHARMACY_NPI,
               "ndcs_sent": [r["ndc"] for r in rx], "fetched": time.strftime("%Y-%m-%d"), "plans": answers}
        (EVALS / "oracle" / f"{persona['name']}.json").write_text(json.dumps(out, indent=1))
        print(f"{persona['name']:22} {len(answers)} plans  (plans where Plan Finder skipped a drug: {partial})")


if __name__ == "__main__":
    main()
