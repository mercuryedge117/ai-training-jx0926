from conftest import load_session

pipeline_mod = load_session("session-03-pipeline-agent", "pipeline")


def test_ignore_bots_drops_bot_messages():
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.ignore_bots)
    calls = []
    result = pipe.run({"ts": "p1", "bot_id": "B1", "text": "x"}, lambda m: calls.append(m))
    assert result is None and calls == []


def test_dedupe_drops_repeated_ts():
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.dedupe)
    seen = []
    pipe.run({"ts": "dup-1", "text": "a"}, lambda m: seen.append(m["ts"]))
    pipe.run({"ts": "dup-1", "text": "a"}, lambda m: seen.append(m["ts"]))
    assert seen == ["dup-1"]


def test_normalize_strips_whitespace():
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.normalize)
    captured = {}
    pipe.run({"ts": "p2", "text": "  hi  "}, lambda m: captured.update(m))
    assert captured["text"] == "hi"


def test_rate_limit_allows_first_three_messages():
    now = [0.0]
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.rate_limit(clock=lambda: now[0]))
    accepted = []

    for index in range(3):
        now[0] = index * 10
        pipe.run({"ts": f"r{index}", "user": "U1", "text": "x"},
                 lambda msg: accepted.append(msg["ts"]))

    assert accepted == ["r0", "r1", "r2"]


def test_rate_limit_blocks_fourth_message_in_rolling_window():
    now = [0.0]
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.rate_limit(clock=lambda: now[0]))
    accepted = []

    for index in range(4):
        now[0] = index * 10
        pipe.run({"ts": f"r{index}", "user": "U1", "text": "x"},
                 lambda msg: accepted.append(msg["ts"]))

    assert accepted == ["r0", "r1", "r2"]


def test_rate_limit_keeps_authors_separate():
    now = [0.0]
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.rate_limit(clock=lambda: now[0]))
    accepted = []

    for index in range(3):
        pipe.run({"ts": f"u1-{index}", "user": "U1", "text": "x"},
                 lambda msg: accepted.append(msg["ts"]))
    pipe.run({"ts": "u2-0", "user": "U2", "text": "x"},
             lambda msg: accepted.append(msg["ts"]))

    assert accepted == ["u1-0", "u1-1", "u1-2", "u2-0"]


def test_rate_limit_allows_message_after_window_expires():
    now = [0.0]
    pipe = pipeline_mod.Pipeline().use(pipeline_mod.rate_limit(clock=lambda: now[0]))
    accepted = []

    for index in range(3):
        pipe.run({"ts": f"r{index}", "user": "U1", "text": "x"},
                 lambda msg: accepted.append(msg["ts"]))
    now[0] = 60
    pipe.run({"ts": "r3", "user": "U1", "text": "x"},
             lambda msg: accepted.append(msg["ts"]))

    assert accepted == ["r0", "r1", "r2", "r3"]


def test_full_pipeline_runs_middlewares_in_order():
    pipe = (pipeline_mod.Pipeline()
            .use(pipeline_mod.ignore_bots)
            .use(pipeline_mod.dedupe)
            .use(pipeline_mod.normalize))
    results = []
    pipe.run({"ts": "p3", "user": "U1", "text": " hello "}, lambda m: results.append(m) or "ok")
    assert results and results[0]["text"] == "hello"
