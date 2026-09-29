"""Build eval personas from evals/persona_specs.json.

For each drug: RxNorm RXCUI + NDC list, plus an `oracle_ndc` = the NDC CMS lists most often for that
RXCUI across formularies (Plan Finder recognizes these). Also writes the non-SNP Miami-Dade plan list.

    PYTHONPATH=src python evals/build_personas.py
"""
from __future__ import annotations

import json
from pathlib import Path

from engine import data, rxnorm

EVALS = Path(__file__).resolve().parent


def main() -> None:
    con = data.connect()
    data.load_market(con, "Florida", "Miami-Dade")
    specs = json.loads((EVALS / "persona_specs.json").read_text())
    for spec in specs:
        drugs = []
        for name, qty in spec["drugs"]:
            info = rxnorm.lookup(name)
            row = con.execute("""
                SELECT ndc, count(*) n FROM formulary WHERE rxcui = ? AND coalesce(trim(ndc), '') <> ''
                GROUP BY ndc ORDER BY n DESC LIMIT 1
            """, [info["rxcui"]]).fetchone()
            drugs.append({"name": name, "qty_per_30d": qty, "rxcui": info["rxcui"],
                          "oracle_ndc": row[0] if row else None, "ndcs": info["ndcs"]})
            flag = "" if row else "   <-- not on any Miami formulary list; oracle will skip"
            print(f"{spec['id']:22} {name[:48]:48} rxcui={info['rxcui']:>8} ndc={row[0] if row else None}{flag}")
        persona = {"name": spec["id"], "desc": spec["desc"], "zip": "33125", "county": "Miami-Dade, FL",
                   "pharmacy": "preferred_retail", "medicaid": False, "chronic_conditions": [],
                   "institutional": False, "drugs": drugs}
        (EVALS / "personas" / f"{spec['id']}.json").write_text(json.dumps(persona, indent=1))

    plans = [p.key for p in data.plans(con) if p.snp_type is None]
    (EVALS / "plans_miami_nonsnp.json").write_text(json.dumps(sorted(plans), indent=1))
    print(f"\nWrote {len(specs)} personas and {len(plans)} non-SNP plans.")


if __name__ == "__main__":
    main()
