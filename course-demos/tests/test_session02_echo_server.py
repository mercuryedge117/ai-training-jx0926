import hashlib
import hmac
import json
import time

from conftest import load_session

echo_server = load_session("session-02-slack-api", "echo_server")


def _sign(body, ts):
    return "v0=" + hmac.new(echo_server.SIGNING_SECRET.encode(),
                             f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()


def _post(client, body, ts, sig):
    return client.post("/slack/events", data=body,
                        headers={"X-Slack-Request-Timestamp": ts,
                                 "X-Slack-Signature": sig,
                                 "Content-Type": "application/json"})


def test_ack_within_3_seconds():
    client = echo_server.app.test_client()
    body = json.dumps({"type": "event_callback", "event_id": "Ev-test-1",
                        "event": {"type": "message", "user": "U1", "text": "hi"}})
    ts = str(int(time.time()))
    t0 = time.time()
    resp = _post(client, body, ts, _sign(body, ts))
    assert resp.status_code == 200
    assert (time.time() - t0) < 3.0


def test_duplicate_event_id_deduped_not_double_processed():
    client = echo_server.app.test_client()
    body = json.dumps({"type": "event_callback", "event_id": "Ev-test-2",
                        "event": {"type": "message", "user": "U1", "text": "hi"}})
    ts = str(int(time.time()))
    sig = _sign(body, ts)
    r1 = _post(client, body, ts, sig)
    r2 = _post(client, body, ts, sig)
    assert r1.status_code == 200 and r2.status_code == 200
    assert "Ev-test-2" in echo_server.seen_event_ids


def test_forged_signature_rejected():
    client = echo_server.app.test_client()
    body = json.dumps({"type": "event_callback", "event_id": "Ev-test-3",
                        "event": {"type": "message", "user": "U1", "text": "hi"}})
    resp = _post(client, body, str(int(time.time())), "v0=forged")
    assert resp.status_code == 401
