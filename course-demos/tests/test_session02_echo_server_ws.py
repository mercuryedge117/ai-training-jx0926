from conftest import load_session


echo_server_ws = load_session("session-02-slack-api", "echo_server_ws")


class FakeClient:
    def __init__(self):
        self.posts = []

    def chat_postMessage(self, **kwargs):
        self.posts.append(kwargs)
        return {"ok": True, "ts": "1700000000.000002"}


def test_build_post_args_replies_in_original_thread():
    event = {"channel": "C1", "ts": "100.001", "thread_ts": "99.001",
             "text": "  <@UBOT> hello  "}
    assert echo_server_ws.build_post_args(event) == {
        "channel": "C1",
        "text": "echo: <@UBOT> hello",
        "thread_ts": "99.001",
    }


def test_top_level_mention_starts_thread():
    event = {"channel": "C1", "ts": "100.001", "text": "hello"}
    assert echo_server_ws.build_post_args(event)["thread_ts"] == "100.001"


def test_process_event_posts_echo_without_network_or_delay():
    client = FakeClient()
    event = {"channel": "C1", "ts": "100.001", "user": "U1", "text": "hello"}
    echo_server_ws.process_event_async(event, client, delay_sec=0)
    assert client.posts == [{"channel": "C1", "text": "echo: hello",
                             "thread_ts": "100.001"}]


def test_bot_messages_are_ignored_to_prevent_reply_loop():
    assert echo_server_ws.should_ignore({"bot_id": "B1"})
    assert echo_server_ws.should_ignore({"subtype": "bot_message"})
    assert not echo_server_ws.should_ignore({"user": "U1", "text": "hello"})


def test_only_human_replies_in_activated_threads_are_processed():
    echo_server_ws.active_threads.clear()
    mention = {"channel": "C1", "ts": "100.001", "text": "<@UBOT> hello"}
    echo_server_ws.activate_thread(mention)

    assert echo_server_ws.should_reply_in_active_thread(
        {"channel": "C1", "thread_ts": "100.001", "ts": "101.001", "text": "follow up"}
    )
    assert not echo_server_ws.should_reply_in_active_thread(
        {"channel": "C1", "thread_ts": "other-thread", "ts": "102.001", "text": "ignore"}
    )
    assert not echo_server_ws.should_reply_in_active_thread(
        {"channel": "C1", "thread_ts": "100.001", "ts": "103.001", "bot_id": "B1"}
    )


def test_message_channels_does_not_process_a_bot_mention_twice():
    event = {"text": "<@UBOT> hello"}
    assert echo_server_ws.mentions_bot(event, "UBOT")
    assert not echo_server_ws.mentions_bot(event, "UOTHER")


def test_event_id_claim_is_atomic_dedupe_boundary():
    event_id = "Ev-ws-test-unique"
    assert echo_server_ws.claim_event(event_id)
    assert not echo_server_ws.claim_event(event_id)
