#!/usr/bin/env python3
"""Session 01: environment self-check.

Teaching point: an enterprise project starts with a reproducible environment.
Every dependency and credential should be verifiable with one command.
"""
import importlib.util
import os
import sys

from dotenv import load_dotenv

load_dotenv()

REQUIRED_PKGS = ["yaml", "flask", "slack_sdk"]
OPTIONAL_PKGS = ["openai", "anthropic", "slack_bolt"]  # slack_bolt: hello_bot.py's real-Slack path
ENV_VARS = {
    "SLACK_BOT_TOKEN": "Slack bot token (xoxb-...) — needed from session 2",
    "SLACK_SIGNING_SECRET": "Slack signing secret — needed from session 2",
    "OPENAI_API_KEY": "LLM key (or ANTHROPIC_API_KEY / DEEPSEEK_API_KEY) — needed from session 3",
    "ANTHROPIC_API_KEY": "alternative LLM key",
    "DEEPSEEK_API_KEY": "alternative LLM key (OpenAI-compatible, deepseek-chat)",
}


def check(label: str, ok: bool, hint: str = ""):
    mark = "OK     " if ok else "MISSING"
    print(f"  [{mark}] {label}" + (f"  ({hint})" if hint and not ok else ""))
    return ok


def main():
    print("== Python ==")
    py_ok = sys.version_info >= (3, 9)
    check(f"Python {sys.version.split()[0]} (need >= 3.9)", py_ok)

    print("== Required packages ==")
    missing = []
    for pkg in REQUIRED_PKGS:
        ok = importlib.util.find_spec(pkg) is not None
        if not ok:
            missing.append(pkg)
        check(pkg, ok, f"pip install {'pyyaml' if pkg == 'yaml' else pkg}")

    print("== Optional LLM packages ==")
    for pkg in OPTIONAL_PKGS:
        check(pkg, importlib.util.find_spec(pkg) is not None, f"pip install {pkg}")

    print("== Environment variables ==")
    for var, hint in ENV_VARS.items():
        check(var, bool(os.environ.get(var)), hint)

    has_llm = (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
               or os.environ.get("DEEPSEEK_API_KEY"))
    print("\nSummary:")
    print(f"  core deps: {'ready' if py_ok and not missing else 'incomplete -> ' + ', '.join(missing)}")
    print(f"  LLM mode: {'real API' if has_llm else 'mock (all demos still runnable)'}")
    print(f"  Slack mode: {'connected' if os.environ.get('SLACK_BOT_TOKEN') else 'console simulation'}")


if __name__ == "__main__":
    main()
