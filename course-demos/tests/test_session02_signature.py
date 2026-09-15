import time

from conftest import load_session

verify_signature = load_session("session-02-slack-api", "verify_signature")


def test_valid_signature_passes():
    now = str(int(time.time()))
    body = '{"a":1}'
    sig = verify_signature.sign(verify_signature.SIGNING_SECRET, now, body)
    ok, reason = verify_signature.verify(verify_signature.SIGNING_SECRET, now, body, sig)
    assert ok and reason == "valid"


def test_tampered_body_fails():
    now = str(int(time.time()))
    sig = verify_signature.sign(verify_signature.SIGNING_SECRET, now, '{"a":1}')
    ok, reason = verify_signature.verify(verify_signature.SIGNING_SECRET, now, '{"a":2}', sig)
    assert not ok and "mismatch" in reason


def test_replayed_timestamp_rejected():
    old = str(int(time.time()) - 600)
    body = '{"a":1}'
    sig = verify_signature.sign(verify_signature.SIGNING_SECRET, old, body)
    ok, reason = verify_signature.verify(verify_signature.SIGNING_SECRET, old, body, sig)
    assert not ok and "replay" in reason
