# Backlog (known issues, deferred on purpose)

Spike result (2026-09-26): 6 of 7 plans within 0.2% of Medicare Plan Finder; worst 5.5%.

| Issue | Impact | Current handling | Fix when |
| --- | --- | --- | --- |
| Pharmacy dispensing fees not included | Brand drugs may be $0-30/month higher; only affects plans with a deductible or coinsurance (e.g. BlueMedicare Select H5434-002 under by 5.5%) | Disclosed in `estimate()` assumptions | W3, with the "choose your pharmacy" UI feature: load dispensing fees from the pharmacy network table |
| Many plans tie at $0 drugs + $0 premium | Ranking can't separate them for low-drug users | Sort by drugs + premium | 10/1: add MOOP and utilization scenarios; W3: add prior-auth denial rate and star rating |
| Plan Finder silently skips NDCs it doesn't know | Oracle may under-count drugs | Use Plan Finder-recognized NDCs in evals | When building the 10 eval personas |
