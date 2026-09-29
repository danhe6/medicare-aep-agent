# Data architecture: keeping plan data current

**Why it matters:** judging runs Dec 1-15, 2026, in the middle of the 2027 Annual Enrollment Period.
Plans change formularies mid-year (e.g. brand Farxiga dropped after its generic launched), so a one-time
download is wrong within weeks. The data layer is a pipeline, not a file.

## Sources and cadence

| Data | Source | Published | Used for |
| --- | --- | --- | --- |
| Plans, formularies, cost sharing, insulin cost | CMS **monthly** Part D PUF | ~4th Wednesday each month; next plan year appears from the October file | Coverage, tiers, copays, deductibles |
| Negotiated drug prices | CMS **quarterly** Part D PUF | Quarterly | Drug cost per unit |
| Drug names -> RXCUI -> NDC | NLM RxNav API | Live | Matching user drugs |
| Star ratings, plan exits, prior-auth denial rates | CMS / insurer sites via Tavily | Annual / live | Ranking context, red flags |

Coverage and prices can come from different releases (and even different plan years). Every release
records both in `manifest.json`, and the engine discloses it ("2026 prices applied to 2027 benefits").

## Pipeline (`pipeline/build.py`)

1. **Discover** the newest monthly and quarterly files in the CMS catalog (`data.cms.gov/data.json`).
2. **Download** once (immutable, cached by file name) and extract only the needed tables.
3. **Build** a self-contained release: `data/releases/m<monthly>_q<quarterly>/*.parquet` + `manifest.json`
   (national, all counties).
4. **Validate**: minimum row counts per table; no table shrinks >30% vs the current release.
5. **Promote** atomically: `data/releases/CURRENT` points to the new release. If validation fails,
   the app keeps serving the previous release.
6. **Regression check** (dev only): `evals/run_eval.py` against the Plan Finder answer key.

The engine reads only `CURRENT`, scoped per request to one county (`data.load_market`).

## Refresh plan through judging

| When | Action |
| --- | --- |
| Now (Sep) | Build from Sep monthly + Q2/Q3 quarterly (2026 plan year) |
| ~Oct 28 | October monthly adds **2027** coverage -> rebuild; default the UI to 2027 |
| Nov, Dec (judging) | Scheduled monthly rebuild (cloud job) -> object storage -> app picks up new `CURRENT` |

Open item: confirm with organizers that automated *data* refreshes after the submission deadline are
allowed (code frozen; the scheduled job is part of the submitted system).
