# Medicare AEP Agent

A neutral, privacy-first Medicare assistant: reads your plan's Annual Notice of Change (ANOC), computes each plan's true annual cost, flags hidden traps, and produces a one-page summary for family.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) — Personal AI track. Runs NVIDIA Nemotron models on Nebius Token Factory.

> Status: in development (MVP scope: Miami-Dade, FL). Decision support only — not an enrollment or brokerage service.

## Repo layout

| Path | Contents |
| --- | --- |
| `docs/` | Plan, scope, friction log, interview notes |
| `data/raw/` | Downloaded CMS public files (gitignored) |
| `data/processed/` | Filtered / derived tables (gitignored) |
| `src/engine/` | Deterministic cost engine (no LLM) |
| `src/agent/` | Nemotron agent, tools, memory |
| `web/` | Front end |
| `evals/` | Test personas and eval harness |
| `notebooks/` | Data exploration |

## Setup

Coming soon. Copy `.env.example` to `.env` and fill in API keys.

## License

MIT — see [LICENSE](LICENSE).
