import pytest

from common.llm import call_llm, llm_available


def test_mock_string_returned_without_keys():
    assert call_llm("sys", "user", mock="canned answer") == "canned answer"


def test_mock_callable_receives_system_and_user():
    out = call_llm("SYS", "USER", mock=lambda s, u: f"{s}|{u}")
    assert out == "SYS|USER"


def test_raises_without_mock_or_keys():
    with pytest.raises(RuntimeError):
        call_llm("sys", "user")


def test_llm_available_reflects_env(monkeypatch):
    assert llm_available() is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_available() is True
