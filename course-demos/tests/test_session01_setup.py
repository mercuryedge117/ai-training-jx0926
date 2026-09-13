from conftest import load_session

check_env = load_session("session-01-setup", "check_env")
hello_bot = load_session("session-01-setup", "hello_bot")


def test_check_env_reports_ok_for_installed_required_packages(capsys):
    check_env.main()
    out = capsys.readouterr().out
    assert "[OK     ] yaml" in out
    assert "[OK     ] flask" in out
    assert "mock (all demos still runnable)" in out


def test_hello_bot_handler_is_transport_agnostic():
    reply = hello_bot.handle_message("U42", "are you there?")
    assert "U42" in reply and "are you there?" in reply


def test_hello_bot_handler_uses_llm_response(monkeypatch):
    calls = []

    def fake_call_llm_safe(system, user, mock, temperature=0.3):
        calls.append((system, user, temperature))
        return "LLM says hello"

    monkeypatch.setattr(hello_bot, "call_llm_safe", fake_call_llm_safe)

    assert hello_bot.handle_message("U42", "explain the demo") == "LLM says hello"
    assert "teaching assistant" in calls[0][0]
    assert "<@U42>" in calls[0][1]
    assert "explain the demo" in calls[0][1]


def test_hello_bot_mock_flag_skips_llm(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM should not be called in mock mode")

    monkeypatch.setattr(hello_bot, "call_llm_safe", fail_if_called)

    reply = hello_bot.handle_message("U42", "<@UBOT> explain the demo", mock=True)
    assert "U42" in reply
    assert "explain the demo" in reply


def test_hello_bot_parse_args_supports_mock_and_console(monkeypatch):
    monkeypatch.setattr("sys.argv", ["hello_bot.py", "--mock", "--console"])
    args = hello_bot.parse_args()
    assert args.mock is True
    assert args.console is True


def test_hello_bot_strips_leading_slack_mentions_before_llm(monkeypatch):
    calls = []

    def fake_call_llm_safe(system, user, mock, temperature=0.3):
        calls.append(user)
        return "clean response"

    monkeypatch.setattr(hello_bot, "call_llm_safe", fake_call_llm_safe)

    assert hello_bot.handle_message("U42", "<@UBOT> explain the demo") == "clean response"
    assert "Slack user <@U42> said:\nexplain the demo" == calls[0]


def test_hello_bot_builds_thread_key_from_mention_event():
    event = {"channel": "C42", "ts": "1700000000.000100", "user": "U42"}
    assert hello_bot.thread_key(event) == ("C42", "1700000000.000100")


def test_hello_bot_answers_human_replies_in_active_threads():
    active_threads = {("C42", "1700000000.000100")}
    event = {
        "channel": "C42",
        "thread_ts": "1700000000.000100",
        "ts": "1700000001.000200",
        "user": "U42",
        "text": "following up without mention",
    }
    assert hello_bot.should_answer_thread_reply(event, active_threads)


def test_hello_bot_ignores_untracked_or_bot_thread_messages():
    active_threads = {("C42", "1700000000.000100")}
    assert not hello_bot.should_answer_thread_reply(
        {"channel": "C42", "thread_ts": "999.000100", "user": "U42"},
        active_threads,
    )
    assert not hello_bot.should_answer_thread_reply(
        {"channel": "C42", "thread_ts": "1700000000.000100", "bot_id": "B42"},
        active_threads,
    )
