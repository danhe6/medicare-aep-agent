"""Read any Medicare letter (photo or PDF) and turn it into: what it is, the deadline, what to do, and a drafted
appeal letter. Design (Anthropic, "Building effective agents"): a ROUTER picks the letter type (keywords first,
LLM only if none match), then a fixed WORKFLOW per type: extract fields (LLM) -> deadlines and steps (rules, no LLM)
-> draft the argument paragraph (LLM) -> check the draft against the facts (code) and redraft once if it fails."""
