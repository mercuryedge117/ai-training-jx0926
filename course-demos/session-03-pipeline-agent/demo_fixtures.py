"""Fixed fixtures and a thread-safe registry of successfully posted seed messages."""
import json
from pathlib import Path
from threading import RLock
from time import monotonic

FIXTURES = Path(__file__).parent / 'fixtures'


def load_manifest(path=None, scenario='short'):
    data = json.loads(Path(path or FIXTURES / f'{scenario}.json').read_text(encoding='utf-8'))
    if not isinstance(data.get('messages'), list) or not data.get('channel_id'):
        raise ValueError('manifest requires channel_id and messages')
    return data


class DemoRegistry:
    def __init__(self, clock=monotonic, pending_limit=100, pending_seconds=5):
        self.lock = RLock()
        self.clock = clock
        self.entries = {}
        self.pending = {}
        self.pending_limit, self.pending_seconds = pending_limit, pending_seconds
        self.active = False
        self.on_ready = lambda msg: None
        self.on_expired = lambda msg: None

    def lookup(self, key):
        with self.lock:
            return self.entries.get(key)

    def register(self, team, channel, ts, actor, run_id):
        with self.lock:
            key = (team, channel, ts)
            self.entries[key] = {'simulation_actor': actor, 'demo_run_id': run_id}
            pending = self.pending.pop(key, None)
        if pending:
            self.on_ready(pending[1])

    def defer(self, msg):
        key = (msg['team_id'], msg['channel'], msg['ts'])
        with self.lock:
            # Registration and defer race: do not miss an already-arrived receipt.
            if key in self.entries:
                return 'ready'
            if not self.active or len(self.pending) >= self.pending_limit:
                return 'rejected'
            self.pending.setdefault(key, (self.clock(), msg))
            return 'pending'

    def expire(self, force=False):
        with self.lock:
            expired = [key for key, (when, _) in self.pending.items()
                       if force or self.clock() - when >= self.pending_seconds]
            rows = [self.pending.pop(key)[1] for key in expired]
        for row in rows:
            self.on_expired(row)


def replay_events(manifest, registry):
    team, channel = 'demo:manifest', manifest['channel_id']
    run_id = manifest.get('demo_run_id', 'fixture')
    for row in manifest['messages']:
        registry.register(team, channel, row['ts'], row.get('actor'), run_id)
        yield {'event_id': 'replay:' + row['ts'], 'team_id': team,
               'event': {'type': 'message', 'channel': channel, 'ts': row['ts'],
                         'thread_ts': row.get('thread_ts'), 'user': 'demo:bot',
                         'bot_id': 'demo:bot-id', 'text': row['text']}}


def summary_event(channel, ts='9999999999.000001', user='fixture:user:alice', audience='engineer'):
    return {'event_id': f'command:{user}:{ts}', 'team_id': 'demo:manifest',
            'event': {'type': 'app_mention', 'channel': channel, 'ts': ts,
                      'user': user, 'text': f'<@demo:bot> summary {audience}'}}
