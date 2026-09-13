#!/usr/bin/env python3
"""Generate simulated Slack messages from scenario skeletons using an LLM.

Reads config/personas.yaml + a scenario YAML, expands each event "beat" into
3-8 natural messages, and appends them to a JSONL file compatible with
inject_slack.py. Also merges each event's ground_truth into an output JSON.

Usage:
  export OPENAI_API_KEY=sk-...        # or ANTHROPIC_API_KEY
  python generate_messages.py config/scenarios/incident_payment_outage.yaml \
      --out data/generated_messages.jsonl --gt-out data/generated_ground_truth.json

Requires: pip install pyyaml openai   (or: pip install pyyaml anthropic)
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent

SYSTEM_TEMPLATE = """You write realistic Slack messages for a simulated engineering team.

Team: {team_name} at {company}, product: {product}.

Team members (use these ids as authors):
{personas}

Rules:
- Output ONLY a JSON array of message objects: {{"author": "<member id>", "text": "<message>", "reply": <true|false>}}
- 3 to 8 messages per request. "reply": true means the message belongs in the thread started by the first message.
- Match each member's described style exactly. Vary message length. Realistic Slack tone: occasional typos are fine for informal personas, code blocks in ``` where natural.
- Never invent members not listed. Never summarize; write the actual messages."""

EVENT_TEMPLATE = """Channel: {channel}
Scene time: {time} on {date}
Participants: {participants}
Tone: {tone}

Scene to act out:
{beat}

Write the Slack messages for this scene now."""


def build_personas_block(personas: dict) -> str:
    lines = []
    for pid, p in personas["members"].items():
        lines.append(f"- {pid}: {p['name']}, {p['role']}. Style: {p['style']}")
    return "\n".join(lines)


def call_llm(system: str, user: str) -> str:
    """Try OpenAI then Anthropic, depending on which key is set."""
    if os.environ.get("OPENAI_API_KEY"):
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=os.environ.get("SIM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.9,
        )
        return resp.choices[0].message.content
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=os.environ.get("SIM_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
    sys.exit("Set OPENAI_API_KEY or ANTHROPIC_API_KEY (or use data/sample_messages.jsonl, which needs no key).")


def parse_json_array(text: str) -> list:
    """Extract the first JSON array from an LLM response."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in LLM output:\n{text[:300]}")
    return json.loads(text[start:end + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", help="Path to scenario YAML")
    ap.add_argument("--personas", default=str(HERE / "config" / "personas.yaml"))
    ap.add_argument("--out", default=str(HERE / "data" / "generated_messages.jsonl"))
    ap.add_argument("--gt-out", default=str(HERE / "data" / "generated_ground_truth.json"))
    args = ap.parse_args()

    personas = yaml.safe_load(Path(args.personas).read_text(encoding="utf-8"))
    scenario = yaml.safe_load(Path(args.scenario).read_text(encoding="utf-8"))

    system = SYSTEM_TEMPLATE.format(
        team_name=personas["team_name"], company=personas["company"],
        product=personas["product"], personas=build_personas_block(personas))

    out_path, gt_path = Path(args.out), Path(args.gt_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ground_truth = {"action_items": [], "risk_alerts": [], "faq": [], "summary_points": []}
    msg_counter = 0
    date = scenario["sim_date"]

    with out_path.open("a", encoding="utf-8") as f:
        for ev in scenario["events"]:
            user_prompt = EVENT_TEMPLATE.format(
                channel=ev["channel"], time=ev["time"], date=date,
                participants=", ".join(ev["participants"]),
                tone=ev.get("tone", "neutral"), beat=ev["beat"].strip())
            print(f"[{scenario['scenario_id']}] generating event {ev['id']} ({ev['channel']} {ev['time']}) ...")
            messages = parse_json_array(call_llm(system, user_prompt))

            thread_root_id = None
            for i, m in enumerate(messages):
                msg_counter += 1
                mid = f"{scenario['scenario_id']}-{ev['id']}-{msg_counter:03d}"
                minute_offset = i  # 1 message per simulated minute
                hh, mm = map(int, ev["time"].split(":"))
                mm_total = hh * 60 + mm + minute_offset
                sim_ts = f"{date}T{mm_total // 60:02d}:{mm_total % 60:02d}:00"
                record = {"id": mid, "sim_ts": sim_ts, "channel": ev["channel"],
                          "author": m["author"], "text": m["text"]}
                if m.get("reply") and thread_root_id:
                    record["thread_root"] = thread_root_id
                elif i == 0:
                    thread_root_id = mid
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            gt = ev.get("ground_truth", {})
            for item in gt.get("action_items", []):
                ground_truth["action_items"].append({**item, "source_event": ev["id"]})
            if "risk_alert" in gt:
                ground_truth["risk_alerts"].append({**gt["risk_alert"], "source_event": ev["id"]})
            for item in gt.get("faq", []):
                ground_truth["faq"].append({**item, "source_event": ev["id"]})
            for point in gt.get("summary_points", []):
                ground_truth["summary_points"].append({"point": point, "source_event": ev["id"]})

    # Merge with existing ground truth file if present
    if gt_path.exists():
        existing = json.loads(gt_path.read_text(encoding="utf-8"))
        for k in ground_truth:
            ground_truth[k] = existing.get(k, []) + ground_truth[k]
    gt_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote messages -> {out_path}")
    print(f"Wrote ground truth -> {gt_path}")


if __name__ == "__main__":
    main()
