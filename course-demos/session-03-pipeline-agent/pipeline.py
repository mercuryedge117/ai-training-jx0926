#!/usr/bin/env python3
"""Session 03: middleware pipeline for message processing.

Instead of one giant handler full of if-statements, each concern (filtering,
dedupe, logging, rate limits) becomes a small middleware that either passes
the message down the chain or stops it. Same idea as Flask/Express middleware.
"""
import time


# Shared core; this file remains the small standalone teaching example.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.message_pipeline import Pipeline


# --- middlewares -----------------------------------------------------------

def ignore_bots(msg, next_):
    if msg.get("bot_id"):
        print(f"  [ignore_bots] dropped bot message {msg['ts']}")
        return None
    return next_(msg)


_seen_ts = set()

def dedupe(msg, next_):
    if msg["ts"] in _seen_ts:
        print(f"  [dedupe] dropped duplicate {msg['ts']}")
        return None
    _seen_ts.add(msg["ts"])
    return next_(msg)


def logger(msg, next_):
    t0 = time.time()
    result = next_(msg)
    print(f"  [logger] {msg['ts']} handled in {(time.time()-t0)*1000:.1f}ms")
    return result


def normalize(msg, next_):
    msg = {**msg, "text": msg.get("text", "").strip()}
    return next_(msg)


# --- demo ------------------------------------------------------------------

def handle(msg):
    print(f"  [handler] REPLY to {msg['user']}: got '{msg['text']}'")
    return "ok"


if __name__ == "__main__":
    pipe = (Pipeline()
            .use(ignore_bots)
            .use(dedupe)
            .use(normalize)
            .use(logger))

    messages = [
        {"ts": "1", "user": "U1", "text": "  hello there  "},
        {"ts": "1", "user": "U1", "text": "  hello there  "},   # duplicate delivery
        {"ts": "2", "user": "U2", "text": "status update", "bot_id": "B9"},  # a bot
        {"ts": "3", "user": "U3", "text": "real question"},
    ]
    for m in messages:
        print(f"incoming {m['ts']}:")
        pipe.run(m, handle)
