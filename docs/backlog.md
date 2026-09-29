# Backlog (known issues, deferred on purpose)

Spike result (2026-09-26): 6 of 7 plans within 0.2% of Medicare Plan Finder; worst 5.5%.

| Issue | Impact | Current handling | Fix when |
| --- | --- | --- | --- |
| Pharmacy dispensing fees not included | Brand drugs may be $0-30/month higher; only affects plans with a deductible or coinsurance (e.g. BlueMedicare Select H5434-002 under by 5.5%) | Disclosed in `estimate()` assumptions | W3, with the "choose your pharmacy" UI feature: load dispensing fees from the pharmacy network table |
| Many plans tie at $0 drugs + $0 premium | Ranking can't separate them for low-drug users | Sort by drugs + premium | 10/1: add MOOP and utilization scenarios; W3: add prior-auth denial rate and star rating |
| Plan Finder silently skips NDCs it doesn't know | Oracle may under-count drugs | Use Plan Finder-recognized NDCs in evals | When building the 10 eval personas |
| Formulary data is from the July quarterly file; plans changed formularies mid-year | Eval 2026-09-26: brand Farxiga covered in our data but NOT_IN_FORMULARY in live Plan Finder for ~30 plans (brand dropped after authorized generic dapagliflozin launched). p05 persona off by ~$12k/yr | Known; Gate 1 still passes (85% OK) | W1: load coverage from the latest **monthly** formulary file (released 4th Wed each month), pricing still from quarterly |
| Plan $35/month insulin cap not modeled; Lantus pen RXCUI not matched to formularies | p03 insulin persona can't be validated | Skipped by oracle | W1: use insulin_cost table + map pen SBD to formulary RXCUIs |

## Product idea from the eval
**Generic-switch alert.** Live Plan Finder: brand Farxiga = not covered, $483/month full price; authorized generic dapagliflozin on the same plan = covered, $0 copay. A user who types "Farxiga" into Plan Finder sees ~$16k/yr for p05. The agent should detect brand -> generic alternatives (RxNorm SBD -> SCD) and say "ask your doctor about the generic; saves ~$5,800/yr on this plan".

## From agent testing (2026-09-26)

| Issue | Seen in | Plan |
| --- | --- | --- |
| Plans with an uncovered drug can still rank #1 when that drug's lower-bound price is small (Leon MediExtra ranked first while not covering Lantus) | Choose, Rosa persona | Stronger penalty / hard rule: a plan that covers every drug (as prescribed or after generic switch) ranks above plans that don't; revisit in UI ranking view |
| Agent adds advice not in tool results ("ask about generic insulin") | Choose | Agent-level eval: flag statements not grounded in tool output; tighten prompt |
| Therapeutic alternatives (Lantus not covered, but Basaglar/Semglee are) not detected | Choose | Look up same-ingredient covered products on the plan's formulary |
| QIO name misread by OCR ("Accentra" vs "Acentra") | Defend | National BFCC-QIO directory (Acentra, Livanta): canonical name from phone number |
| Answers too long for a stressed family | Defend + Choose | UI: countdown + "call now" button + checklist cards; agent text limited to 2-3 sentences |
| Only NOMNC supported | Defend | Add hospital discharge notice (IM); MA prior-auth denial on roadmap |

## Health profile (added 2026-09-27)
- Profile lives ONLY in the browser (localStorage `mh_profile_v1`), sent with each chat turn, never stored server-side.
- TODO before deploy: turn OFF `logs/agent_trace.jsonl` in production (it records tool args incl. update_profile) or redact.
- TODO: encrypt at rest on device (Web Crypto + optional PIN); export/import file or QR so a family member can take over.
- TODO: label reader for insulin/inhaler boxes (units/day directions tested in code only), multi-label photo.
- TODO: next AEP: proactive "your plan changed" check using saved meds (ANOC compare).
- Health usage is now inferred (engine/usage.py) - verify the thresholds against eval personas.
