import pytest

from conftest import SLACK_SIM, load_module

generate_messages = load_module(SLACK_SIM, "generate_messages")


def test_build_personas_block_lists_every_member():
    personas = generate_messages.yaml.safe_load(
        (SLACK_SIM / "config" / "personas.yaml").read_text(encoding="utf-8"))
    block = generate_messages.build_personas_block(personas)
    assert "sarah" in block and "Sarah Chen" in block


def test_parse_json_array_extracts_array_from_prose():
    text = 'Here is the scene:\n[{"author": "sarah", "text": "rolling back now", "reply": false}]'
    parsed = generate_messages.parse_json_array(text)
    assert parsed == [{"author": "sarah", "text": "rolling back now", "reply": False}]


def test_parse_json_array_raises_when_no_array_present():
    with pytest.raises(ValueError):
        generate_messages.parse_json_array("no json here")
