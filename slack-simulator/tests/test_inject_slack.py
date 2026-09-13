from conftest import SLACK_SIM, load_module

inject_slack = load_module(SLACK_SIM, "inject_slack")


def test_load_personas_reads_team_config():
    personas = inject_slack.load_personas()
    assert "sarah" in personas["members"] or "members" in personas


def test_load_messages_sorts_by_sim_ts():
    msgs = inject_slack.load_messages(str(SLACK_SIM / "data" / "sample_messages.jsonl"))
    timestamps = [m["sim_ts"] for m in msgs]
    assert timestamps == sorted(timestamps)
    assert len(msgs) > 0


def test_dry_run_prints_without_requiring_a_slack_token(monkeypatch, capsys):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["inject_slack.py",
                                     str(SLACK_SIM / "data" / "sample_messages.jsonl"),
                                     "--dry-run"])
    inject_slack.main()
    out = capsys.readouterr().out
    assert "Loaded" in out and "#incidents" in out
