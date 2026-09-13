#!/usr/bin/env python3
"""Session 01: hello-world bot.

With SLACK_BOT_TOKEN + SLACK_APP_TOKEN (Socket Mode): responds to @mentions.
After a mention starts a thread, replies in that same thread do not need to
mention the bot again.
Without tokens: console simulation, same handler logic — the teaching point
is that handler code should not care where the message came from.
"""
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional, Set, Tuple

from dotenv import load_dotenv

COURSE_DEMOS = Path(__file__).resolve().parent.parent
if str(COURSE_DEMOS) not in sys.path:
    sys.path.insert(0, str(COURSE_DEMOS))

from common.llm import call_llm_safe

load_dotenv()

SYSTEM_PROMPT = (
    "You are a concise, friendly teaching assistant inside Slack. "
    "Answer the user's message directly. Keep replies under 120 words unless "
    "the user asks for detail."
)


def clean_message_text(text: str) -> str:
    """Remove leading Slack mention tokens before handing text to the bot brain."""
    cleaned = re.sub(r"^(<@[A-Z0-9]+>\s*)+", "", text).strip()
    return cleaned or text.strip()


def mock_reply(user: str, text: str) -> str:
    return f"Hello <@{user}>! You said: “{text}”. I'm alive and listening."


def handle_message(user: str, text: str, mock: bool = False) -> str:
    """The bot's 'brain' — shared by both transports."""
    message_text = clean_message_text(text)
    if mock:
        return mock_reply(user, message_text)

    user_prompt = f"Slack user <@{user}> said:\n{message_text}"
    return call_llm_safe(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        mock=lambda _system, _user: mock_reply(user, message_text),
    )


ThreadKey = Tuple[str, str]


def thread_key(event: dict) -> Optional[ThreadKey]:
    """Return a stable Slack thread identity for events that can live in a thread."""
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    if not channel or not thread_ts:
        return None
    return channel, thread_ts


def should_answer_thread_reply(event: dict, active_threads: Set[ThreadKey]) -> bool:
    """True when a human replied inside a thread the bot is already part of."""
    if not event.get("thread_ts"):
        return False
    if event.get("subtype") or event.get("bot_id") or not event.get("user"):
        return False
    key = thread_key(event)
    return key in active_threads if key else False


def run_console(mock: bool = False):
    print("Console mode (no Slack tokens). Type a message, 'quit' to exit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except EOFError:
            break
        if text.lower() in ("quit", "exit", ""):
            break
        print("bot>", handle_message("console_user", text, mock=mock))


def run_slack(mock: bool = False):
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    active_threads: Set[ThreadKey] = set()

    @app.event("app_mention")
    def on_mention(event, say):
        key = thread_key(event)
        if key:
            active_threads.add(key)
        say(handle_message(event["user"], event["text"], mock=mock),
            thread_ts=(event.get("thread_ts") or event.get("ts")))

    @app.event("message")
    def on_thread_reply(event, say):
        if should_answer_thread_reply(event, active_threads):
            say(handle_message(event["user"], event["text"], mock=mock),
                thread_ts=event["thread_ts"])

    print("Connecting to Slack via Socket Mode...")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


def parse_args():
    parser = ArgumentParser(description="Session 01 Slack/console hello bot.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="force offline echo responses instead of calling a real LLM",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="run console mode even when Slack tokens are configured",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if (not args.console and os.environ.get("SLACK_BOT_TOKEN")
            and os.environ.get("SLACK_APP_TOKEN")):
        run_slack(mock=args.mock)
    else:
        run_console(mock=args.mock)
