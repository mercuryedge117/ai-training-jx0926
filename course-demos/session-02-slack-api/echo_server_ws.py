#!/usr/bin/env python3
"""Session 02: receive and echo Slack app mentions over Socket Mode.

Unlike echo_server.py, this version needs no public HTTP endpoint or signing
secret. The process opens an outbound WebSocket using SLACK_APP_TOKEN; Slack
delivers subscribed Events API events over that connection. SLACK_BOT_TOKEN is
used to post the echo back to Slack.

Run modes:
  python echo_server_ws.py --test  # offline self-test; makes no Slack calls
  python echo_server_ws.py         # connect to Slack via Socket Mode
"""
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

seen_event_ids = set()
seen_event_ids_lock = threading.Lock()
active_threads = set()
active_threads_lock = threading.Lock()


def require_env(name: str) -> str:
    """Return a required environment variable or stop with a useful message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before starting Socket Mode.")
    return value


def claim_event(event_id) -> bool:
    """Atomically claim an event ID so a redelivery is processed only once."""
    if not event_id:
        return True
    with seen_event_ids_lock:
        if event_id in seen_event_ids:
            return False
        seen_event_ids.add(event_id)
        return True


def should_ignore(event: dict) -> bool:
    """Ignore messages created by bots to prevent self-reply loops."""
    return bool(event.get("bot_id") or event.get("subtype"))


def thread_key(event: dict) -> tuple[str, str] | None:
    """Return the channel and root timestamp that identify a Slack thread."""
    channel = event.get("channel")
    root_ts = event.get("thread_ts") or event.get("ts")
    if not channel or not root_ts:
        return None
    return channel, root_ts


def activate_thread(event: dict) -> None:
    """Remember the thread containing an app mention for this process run."""
    key = thread_key(event)
    if key:
        with active_threads_lock:
            active_threads.add(key)


def should_reply_in_active_thread(event: dict) -> bool:
    """Return whether this is a human reply in a previously activated thread."""
    if should_ignore(event) or not event.get("thread_ts"):
        return False
    key = thread_key(event)
    if key is None:
        return False
    with active_threads_lock:
        return key in active_threads


def mentions_bot(event: dict, bot_user_id: str | None) -> bool:
    """A mention is handled by the app_mention listener, not message.channels."""
    return bool(bot_user_id and f"<@{bot_user_id}>" in event.get("text", ""))


def build_post_args(event: dict) -> dict:
    """Translate an app_mention event into chat.postMessage arguments."""
    channel = event.get("channel")
    if not channel:
        raise ValueError("Slack event has no channel")

    text = event.get("text", "").strip()
    args = {"channel": channel, "text": f"echo: {text}"}

    # Keep the response in the original thread. A top-level mention starts one.
    thread_ts = event.get("thread_ts") or event.get("ts")
    if thread_ts:
        args["thread_ts"] = thread_ts
    return args


def process_event_async(event: dict, client, delay_sec: float = 2.0):
    """Simulate slow work, then send the echo through Slack's Web API."""
    print(f"  [worker] processing message from {event.get('user', '?')}: "
          f"{event.get('text', '')!r} ... ({delay_sec:g}s of pretend LLM work)")
    time.sleep(delay_sec)
    args = build_post_args(event)
    client.chat_postMessage(**args)
    print(f"  [worker] replied in {args['channel']}: {args['text']!r}")


def dispatch_event(body: dict, event: dict, client, logger=None) -> bool:
    """Validate/dedupe quickly and hand slow work to a background thread."""
    if should_ignore(event):
        return False

    event_id = body.get("event_id")
    if not claim_event(event_id):
        return False

    def work():
        try:
            process_event_async(event, client)
        except Exception:  # background exceptions otherwise disappear silently
            if logger:
                logger.exception("Failed to process Slack event %s", event_id)
            else:
                raise

    threading.Thread(target=work, daemon=True).start()
    return True


def create_app():
    """Build the Bolt app without opening a network connection."""
    from slack_bolt import App

    app = App(token=require_env("SLACK_BOT_TOKEN"))

    @app.event("app_mention")
    def on_app_mention(body, event, client, logger):
        # Bolt acknowledges Events API envelopes; this listener returns quickly
        # after starting the worker, keeping acknowledgement comfortably <3s.
        activate_thread(event)
        dispatch_event(body, event, client, logger)

    @app.event("message")
    def on_thread_message(body, event, client, logger, context):
        # A mention opens the thread; later human replies use the same async path.
        # Slack delivers a mention through both subscriptions when message.channels
        # is enabled. Let app_mention handle that one so it is echoed only once.
        if not mentions_bot(event, context.bot_user_id) and should_reply_in_active_thread(event):
            dispatch_event(body, event, client, logger)

    return app


def run_socket_mode():
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app_token = require_env("SLACK_APP_TOKEN")
    print("Connecting to Slack via Socket Mode; no public endpoint is required...")
    SocketModeHandler(create_app(), app_token).start()


def self_test():
    class FakeClient:
        def __init__(self):
            self.posts = []

        def chat_postMessage(self, **kwargs):
            self.posts.append(kwargs)
            return {"ok": True, "ts": "1700000000.000002"}

    client = FakeClient()
    event = {"type": "app_mention", "user": "U42", "channel": "C42",
             "ts": "1700000000.000001", "text": "<@U-BOT> hello bot"}
    process_event_async(event, client, delay_sec=0)
    post = client.posts[0]
    print(f"[test] posted {post['text']!r} to {post['channel']} "
          f"in thread {post['thread_ts']}")
    print("[test] Socket Mode self-test passed (no network calls)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        self_test()
    else:
        run_socket_mode()
