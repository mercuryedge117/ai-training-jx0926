#!/usr/bin/env python3
"""Inject simulated messages into a Slack workspace.

Modes:
  batch     (default) post all messages as fast as rate limits allow
  realtime  replay along the simulated clock, accelerated by --speed
  dry-run   print what would be posted, no Slack calls (no token needed)

Author identity:
  - Default: one bot token, messages prefixed "*Sarah Chen:* ..." so authorship
    is visible and parseable by student bots.
  - Better realism: per-member bot tokens in config/tokens.yaml
    (member_id -> xoxb-token); each member then posts as their own app. If
    your workspace allows chat:write.customize, the single-token mode also
    sets username/icon per member automatically.

Setup (single-token mode):
  1. Create a Slack app at https://api.slack.com/apps -> From scratch.
  2. OAuth scopes (Bot Token): chat:write, chat:write.customize,
     channels:manage, channels:read, channels:join
  3. Install to workspace, copy the xoxb- token.
  4. Set SLACK_BOT_TOKEN=xoxb-... in course-demos/.env (loaded automatically).

Usage:
  python inject_slack.py data/sample_messages.jsonl --dry-run
  python inject_slack.py data/sample_messages.jsonl                  # batch
  python inject_slack.py data/sample_messages.jsonl --realtime --speed 60

Requires: pip install slack_sdk pyyaml
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent

load_dotenv(HERE.parent / "course-demos" / ".env")


def load_personas():
    import yaml
    return yaml.safe_load((HERE / "config" / "personas.yaml").read_text(encoding="utf-8"))


def load_tokens():
    """Optional per-member tokens: config/tokens.yaml -> {member_id: xoxb-...}"""
    p = HERE / "config" / "tokens.yaml"
    if p.exists():
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def load_messages(path: str):
    msgs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                msgs.append(json.loads(line))
    msgs.sort(key=lambda m: m["sim_ts"])
    return msgs


class SlackInjector:
    def __init__(self, personas, tokens):
        from slack_sdk import WebClient
        self.personas = personas["members"]
        self.default_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self.member_clients = {mid: WebClient(token=tok) for mid, tok in tokens.items()}
        self.channel_ids = {}      # "#name" -> C123
        self.thread_ts = {}        # message id -> posted Slack ts
        self.can_customize = None  # detected on first post

    def ensure_channel(self, name: str) -> str:
        if name in self.channel_ids:
            return self.channel_ids[name]
        bare = name.lstrip("#")
        resp = self.default_client.conversations_list(types="public_channel", limit=1000)
        for ch in resp["channels"]:
            if ch["name"] == bare:
                self.channel_ids[name] = ch["id"]
                break
        else:
            created = self.default_client.conversations_create(name=bare)
            self.channel_ids[name] = created["channel"]["id"]
            print(f"  created channel {name}")
        try:
            self.default_client.conversations_join(channel=self.channel_ids[name])
        except Exception:
            pass
        return self.channel_ids[name]

    def post(self, msg: dict):
        from slack_sdk.errors import SlackApiError
        channel_id = self.ensure_channel(msg["channel"])
        member = self.personas.get(msg["author"], {})
        display = member.get("name", msg["author"])
        client = self.member_clients.get(msg["author"], self.default_client)
        using_own_token = msg["author"] in self.member_clients

        kwargs = {"channel": channel_id, "text": msg["text"]}
        if root := msg.get("thread_root"):
            if root in self.thread_ts:
                kwargs["thread_ts"] = self.thread_ts[root]

        if not using_own_token:
            if self.can_customize is not False:
                kwargs["username"] = display
                kwargs["icon_emoji"] = ":bust_in_silhouette:"
            else:
                kwargs["text"] = f"*{display}:* {msg['text']}"

        try:
            resp = client.chat_postMessage(**kwargs)
        except SlackApiError as e:
            err = e.response.get("error", "")
            if err in ("missing_scope", "invalid_arguments") and "username" in kwargs:
                # workspace forbids chat:write.customize -> fall back to prefix mode
                self.can_customize = False
                kwargs.pop("username", None)
                kwargs.pop("icon_emoji", None)
                kwargs["text"] = f"*{display}:* {msg['text']}"
                resp = client.chat_postMessage(**kwargs)
            elif err == "ratelimited":
                delay = int(e.response.headers.get("Retry-After", 30))
                print(f"  rate limited, sleeping {delay}s")
                time.sleep(delay)
                resp = client.chat_postMessage(**kwargs)
            else:
                raise
        else:
            if self.can_customize is None and not using_own_token:
                self.can_customize = True

        self.thread_ts[msg["id"]] = resp["ts"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("messages", help="Path to messages JSONL")
    ap.add_argument("--realtime", action="store_true",
                    help="Replay along the simulated clock instead of batch")
    ap.add_argument("--speed", type=float, default=60.0,
                    help="Realtime acceleration factor (60 = 1 sim minute per real second)")
    ap.add_argument("--delay", type=float, default=1.1,
                    help="Batch mode: seconds between posts (Slack tier-3 limit ~1/s)")
    ap.add_argument("--dry-run", action="store_true", help="Print instead of posting")
    args = ap.parse_args()

    msgs = load_messages(args.messages)
    personas = load_personas()
    print(f"Loaded {len(msgs)} messages across "
          f"{len({m['channel'] for m in msgs})} channels.")

    if args.dry_run:
        for m in msgs:
            name = personas["members"].get(m["author"], {}).get("name", m["author"])
            thread = f" (reply->{m['thread_root']})" if m.get("thread_root") else ""
            print(f"[{m['sim_ts']}] {m['channel']} {name}{thread}: {m['text'][:80]}")
        return

    if not os.environ.get("SLACK_BOT_TOKEN"):
        sys.exit("Set SLACK_BOT_TOKEN (see header of this file for setup steps).")

    injector = SlackInjector(personas, load_tokens())
    prev_ts = None
    for i, m in enumerate(msgs, 1):
        if args.realtime and prev_ts:
            gap = (datetime.fromisoformat(m["sim_ts"])
                   - datetime.fromisoformat(prev_ts)).total_seconds()
            time.sleep(max(gap / args.speed, 0))
        elif prev_ts:
            time.sleep(args.delay)
        injector.post(m)
        prev_ts = m["sim_ts"]
        print(f"  [{i}/{len(msgs)}] {m['channel']} {m['id']}")

    print("Done.")


if __name__ == "__main__":
    main()
