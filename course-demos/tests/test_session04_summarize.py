import math

from conftest import load_session

summarize_mod = load_session("session-04-summarization", "summarize")


def test_load_channel_filters_by_channel():
    msgs = summarize_mod.load_channel("#incidents")
    assert msgs and all(m["channel"] == "#incidents" for m in msgs)


def test_summarize_single_mock_produces_nonempty_output():
    msgs = summarize_mod.load_channel("#incidents")[:5]
    out = summarize_mod.summarize_single(msgs)
    assert isinstance(out, str) and len(out) > 0


def test_map_reduce_reports_correct_chunk_count(capsys):
    msgs = summarize_mod.load_channel("#incidents")
    chunk_size = 5
    summarize_mod.summarize_map_reduce(msgs, chunk_size)
    out = capsys.readouterr().out
    expected = math.ceil(len(msgs) / chunk_size)
    assert f"-> {expected} chunks" in out
