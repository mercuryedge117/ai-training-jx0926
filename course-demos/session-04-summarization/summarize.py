#!/usr/bin/env python3
"""Session 04: channel summarization — single-shot vs map-reduce.

Consumes real simulated data from ../../slack-simulator/. When a conversation
fits the context window: one call. When it doesn't: Map (summarize each chunk)
then Reduce (summarize the summaries). The demo makes both paths visible.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

SIM_DATA = Path(__file__).resolve().parents[2] / "slack-simulator" / "data" / "sample_messages.jsonl"


def load_channel(channel: str):
    msgs = [json.loads(l) for l in SIM_DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [m for m in msgs if m["channel"] == channel]


# Shared implementation also accepts live Pipeline snapshots.
from common.summarization import (
    transcript, mock_summary_fn, summarize_single, summarize_map_reduce,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="#incidents")
    ap.add_argument("--chunk-size", type=int, default=25,
                    help="messages per chunk; conversations larger than this go map-reduce")
    args = ap.parse_args()

    if args.chunk_size < 1:
        ap.error("--chunk-size must be positive")

    msgs = load_channel(args.channel)
    if not msgs:
        sys.exit(f"No messages in {args.channel}. Try #incidents, #product, #engineering.")
    print(f"Loaded {len(msgs)} messages from {args.channel}\n")

    if len(msgs) <= args.chunk_size:
        summary = summarize_single(msgs)
    else:
        summary = summarize_map_reduce(msgs, args.chunk_size)

    print("\n===== SUMMARY =====")
    print(summary)


if __name__ == "__main__":
    main()
