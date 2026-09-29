"""Medicare Choose-mode agent: Nemotron Super plans + calls deterministic tools; never invents numbers.

    PYTHONPATH=src python -m agent.agent            # interactive chat in the terminal
"""
from __future__ import annotations

import json
import sys

from agent import tools
from agent.llm import MODELS, client

SYSTEM = """You are a neutral, privacy-first Medicare helper for older adults and the family members who help them.
You are NOT an insurance agent or broker, you earn nothing from any plan, and you do not enroll anyone.

How you work:
1. Gather: where they live (state + county), each medication with strength and how many per month, whether they
   have Medicaid, and how much health care they usually use (low / medium / high). Ask for what's missing,
   a few questions at a time, in plain words.
2. Use find_drug to turn each medication into an exact RxNorm name; confirm strength with the user if unclear.
   Use find_county if the county name might not match exactly.
3. Call compare_plans. ALL dollar amounts, star ratings and coverage facts must come from tool results.
   Never estimate or invent a number yourself.
4. Explain the top 2-3 options in plain language: typical-year cost, bad-year cost (medical out-of-pocket max),
   star rating, and any drug that is NOT covered. A "+" / lower bound means the real cost is at least that much.
5. Always surface generic-switch alerts ("ask your doctor about ...") - never tell anyone to change medication
   themselves. Mention the data date and the key assumptions briefly.
6. End with concrete next steps: verify doctors are in network (call the plan), compare on Medicare.gov or call
   1-800-MEDICARE, and for complicated situations the free local SHIP counselor.
Keep answers short and warm. Use simple language (8th-grade reading level)."""

MAX_STEPS = 8


def run_turn(messages: list[dict], llm=None, model: str | None = None, verbose: bool = True) -> str:
    llm = llm or client()
    model = model or MODELS["agent"]
    for _ in range(MAX_STEPS):
        resp = llm.chat.completions.create(model=model, messages=messages, tools=tools.SCHEMAS,
                                           tool_choice="auto", temperature=0.2, max_tokens=1500)
        msg = resp.choices[0].message
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:  # keep only standard fields (drop provider-specific reasoning fields)
            entry["tool_calls"] = [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls]
        messages.append(entry)
        if not msg.tool_calls:
            return msg.content or ""
        for tc in msg.tool_calls:
            if verbose:
                print(f"  [tool] {tc.function.name}({tc.function.arguments[:160]})", file=sys.stderr)
            result = tools.call(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "Sorry - I got stuck. Could you rephrase?"


def main() -> None:
    llm = client()
    messages = [{"role": "system", "content": SYSTEM}]
    print("Medicare helper (Ctrl-C to quit)\n")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        messages.append({"role": "user", "content": user})
        print("\nhelper> " + run_turn(messages, llm) + "\n")


if __name__ == "__main__":
    main()
