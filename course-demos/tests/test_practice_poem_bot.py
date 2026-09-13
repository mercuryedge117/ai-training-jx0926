from pathlib import Path

from conftest import load_module

poem_bot = load_module(
    Path(__file__).resolve().parents[1] / "session-01-setup" / "practices",
    "session_01_poem_bot",
)


def test_poem_bot_mock_reply_is_deterministic():
    reply = poem_bot.answer_with_poem("我今天很想家", mock=True)
    assert "举头望明月，低头思故乡" in reply
    assert "说明：" in reply


def test_poem_bot_uses_shared_llm_entry(monkeypatch):
    calls = []

    def fake_call_llm_safe(system, user, mock, temperature=0.3):
        calls.append((system, user, temperature))
        return "诗句：海上生明月，天涯共此时。\n说明：适合远方思念。"

    monkeypatch.setattr(poem_bot, "call_llm_safe", fake_call_llm_safe)

    reply = poem_bot.answer_with_poem("我在远方想念朋友")
    assert "海上生明月" in reply
    assert "中文诗词聊天机器人" in calls[0][0]
    assert "我在远方想念朋友" in calls[0][1]
    assert calls[0][2] == 0.2


def test_poem_bot_diagram_mentions_implemented_files():
    assert "session_01_poem_bot.py" in poem_bot.ARCHITECTURE_MERMAID
    assert "course-demos/common/llm.py" in poem_bot.ARCHITECTURE_MERMAID
    assert "course-demos/.env" in poem_bot.ARCHITECTURE_MERMAID
    assert "古诗词回答" in poem_bot.ARCHITECTURE_MERMAID
    assert "call_llm_safe" not in poem_bot.ARCHITECTURE_MERMAID
    assert "API失败" not in poem_bot.ARCHITECTURE_MERMAID


def test_poem_bot_parse_args_supports_diagram(monkeypatch):
    monkeypatch.setattr("sys.argv", ["session_01_poem_bot.py", "--diagram"])
    args = poem_bot.parse_args()
    assert args.diagram is True
