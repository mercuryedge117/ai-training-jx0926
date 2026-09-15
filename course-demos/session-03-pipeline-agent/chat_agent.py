#!/usr/bin/env python3
"""Session 03: conversational agent with context-window management.

Teaching point: memory is a cost decision. Every turn you keep = tokens you
pay for on every subsequent call. Strategy here: keep the last N turns
verbatim; older turns get folded into a one-line rolling summary.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common.llm import call_llm

MAX_TURNS = 6          # keep this many recent (user, bot) exchanges verbatim


class ConversationMemory:
    def __init__(self, max_turns=MAX_TURNS):
        self.turns = []            # [(role, text)]
        self.rolling_summary = ""
        self.max_turns = max_turns

    def add(self, role, text):
        self.turns.append((role, text))
        self.truncate()

    def truncate(self):
        """Fold overflow turns into the rolling summary instead of dropping them."""
        while len(self.turns) > self.max_turns * 2:
            role, text = self.turns.pop(0)
            self.rolling_summary = (self.rolling_summary + f" {role}: {text[:60]};")[-500:]

    def as_prompt(self):
        lines = []
        if self.rolling_summary:
            lines.append(f"(earlier conversation, summarized: {self.rolling_summary})")
        lines += [f"{r}: {t}" for r, t in self.turns]
        return "\n".join(lines)


def reply(memory: ConversationMemory, user_text: str) -> str:
    memory.add("user", user_text)
    answer = call_llm(
        system="You are a helpful team assistant inside Slack. Be concise.",
        user=memory.as_prompt(),
        mock=lambda s, u: f"(mock) I hear you — you said '{user_text}'. "
                          f"Context size: {len(memory.turns)} turns"
                          + (f", plus summarized history" if memory.rolling_summary else ""))
    memory.add("assistant", answer)
    return answer


if __name__ == "__main__":
    mem = ConversationMemory()
    print("Chat agent REPL — 'quit' to exit. Watch the context stay bounded.\n")
    scripted = ["hi, who are you?", "what did we deploy today?", "remind me tomorrow",
                "and what about the incident?", "summarize this chat", "thanks",
                "one more thing", "actually two more things"]
    interactive = sys.stdin.isatty()
    for i in range(100):
        if interactive:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
        else:
            if i >= len(scripted):
                break
            text = scripted[i]
            print(f"you> {text}")
        if text.lower() in ("quit", "exit", ""):
            break
        print("bot>", reply(mem, text))
        print(f"     [memory: {len(mem.turns)} turns kept, "
              f"summary buffer {len(mem.rolling_summary)} chars]")
