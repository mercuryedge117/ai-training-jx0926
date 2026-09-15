"""Explicitly seed a running demo; never write directly into MessageStore."""
import json
import time
from pathlib import Path

from demo_fixtures import load_manifest
from slack_adapter import post_message


def seed(client, registry, team, channel, run_id, output, scenario='short'):
    fixture = load_manifest(scenario=scenario)
    path = Path(output) / 'manifest.json'
    data = {'demo_run_id': run_id, 'team_id': team, 'channel_id': channel, 'messages': []}
    registry.active = True
    try:
        for row in fixture['messages']:
            response = post_message(client, channel=channel, text=row['text'],
                                    unfurl_links=False, unfurl_media=False)
            posted = {'channel': channel, 'ts': response['ts'], 'text': row['text'],
                      'actor': row.get('actor')}
            data['messages'].append(posted)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)
            registry.register(team, channel, posted['ts'], posted['actor'], run_id)
            time.sleep(1.1)  # Small, explicit classroom batch; do not flood Slack.
    finally:
        registry.active = False
    return len(data['messages'])
