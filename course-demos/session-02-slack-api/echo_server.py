#!/usr/bin/env python3
"""Session 02: Events API endpoint with the ack-then-process pattern.

Slack retries any event not acknowledged within 3 seconds — so the handler
must return 200 immediately and do real work (LLM calls take seconds!) on a
background worker. This exact pattern generalizes to most webhook platforms.

Run modes:
  python echo_server.py --test    # self-test with a signed fake request
  python echo_server.py           # real server on :3000 (expose via ngrok)
"""
import hashlib
import hmac
import json
import os
import sys
import threading
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "demo-signing-secret")
app = Flask(__name__)
seen_event_ids = set()          # dedupe: Slack retries deliver the same event_id


def verify_request(body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp or 0)) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(SIGNING_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def process_event_async(event: dict):
    """Simulates slow work (LLM call, DB write). Runs OFF the request thread."""
    print(f"  [worker] processing message from {event.get('user', '?')}: "
          f"{event.get('text', '')!r} ... (2s of pretend LLM work)")
    time.sleep(2)
    print(f"  [worker] done. would reply: 'echo: {event.get('text', '')}'")


@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not verify_request(request.get_data(),
                          request.headers.get("X-Slack-Request-Timestamp"),
                          request.headers.get("X-Slack-Signature")):
        return "invalid signature", 401

    payload = request.get_json()
    if payload.get("type") == "url_verification":        # Slack's one-time handshake
        return jsonify({"challenge": payload["challenge"]})

    event_id = payload.get("event_id")
    if event_id in seen_event_ids:                       # retry dedupe
        return "", 200
    seen_event_ids.add(event_id)

    threading.Thread(target=process_event_async,
                     args=(payload.get("event", {}),), daemon=True).start()
    return "", 200                                       # ack in <3s — the whole point


def self_test():
    body = json.dumps({"type": "event_callback", "event_id": "Ev123",
                       "event": {"type": "message", "user": "U42", "text": "hello bot"}})
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(SIGNING_SECRET.encode(),
                           f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
    client = app.test_client()

    t0 = time.time()
    resp = client.post("/slack/events", data=body, headers={
        "X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig,
        "Content-Type": "application/json"})
    ack_ms = (time.time() - t0) * 1000
    print(f"[test] ack status={resp.status_code} in {ack_ms:.0f}ms (must be <3000ms)")

    resp2 = client.post("/slack/events", data=body, headers={
        "X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig,
        "Content-Type": "application/json"})
    print(f"[test] duplicate delivery ack={resp2.status_code} (deduped, no double work)")

    bad = client.post("/slack/events", data=body, headers={
        "X-Slack-Request-Timestamp": ts, "X-Slack-Signature": "v0=forged",
        "Content-Type": "application/json"})
    print(f"[test] forged signature rejected with {bad.status_code}")

    time.sleep(2.5)  # let the worker finish so its prints show


if __name__ == "__main__":
    if "--test" in sys.argv:
        self_test()
    else:
        app.run(port=3000)
