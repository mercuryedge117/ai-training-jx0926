from conftest import load_session

chat_agent = load_session("session-03-pipeline-agent", "chat_agent")


def test_truncate_folds_overflow_into_rolling_summary():
    mem = chat_agent.ConversationMemory(max_turns=2)
    for i in range(10):
        mem.add("user", f"msg{i}")
    assert len(mem.turns) <= 4
    assert mem.rolling_summary != ""
    assert len(mem.rolling_summary) <= 500


def test_reply_mock_echoes_input_and_appends_both_turns():
    mem = chat_agent.ConversationMemory()
    out = chat_agent.reply(mem, "what did we deploy today?")
    assert "what did we deploy today?" in out
    assert len(mem.turns) == 2
    assert mem.turns[0] == ("user", "what did we deploy today?")
    assert mem.turns[1][0] == "assistant"
