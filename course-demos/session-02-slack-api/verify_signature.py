#!/usr/bin/env python3
"""Session 02: Slack request signature verification (HMAC-SHA256).

Slack signs every request: v0=HMAC_SHA256(secret, "v0:{timestamp}:{body}").
Verifying it prevents forged webhooks; checking the timestamp prevents replay.
"""
import hashlib
import hmac
import time

SIGNING_SECRET = "demo-signing-secret"


def sign(secret: str, timestamp: str, body: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, body: str, signature: str,
           tolerance_sec: int = 300) -> tuple[bool, str]:
    if abs(time.time() - int(timestamp)) > tolerance_sec:
        return False, "stale timestamp (possible replay attack)"
    expected = sign(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):   # constant-time compare!
        return False, "signature mismatch (body tampered or wrong secret)"
    return True, "valid"


def demo():
    body = '{"type":"event_callback","event":{"type":"message","text":"hi"}}'
    now = str(int(time.time()))

    print("Case 1 — legitimate request:")
    sig = sign(SIGNING_SECRET, now, body)
    print("  ", verify(SIGNING_SECRET, now, body, sig))

    print("Case 2 — body tampered in transit:")
    tampered = body.replace("hi", "send $$ to attacker")
    print("  ", verify(SIGNING_SECRET, now, tampered, sig))

    print("Case 3 — replayed request from 10 minutes ago:")
    old = str(int(time.time()) - 600)
    old_sig = sign(SIGNING_SECRET, old, body)
    print("  ", verify(SIGNING_SECRET, old, body, old_sig))


if __name__ == "__main__":
    demo()
