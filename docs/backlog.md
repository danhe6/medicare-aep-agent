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
