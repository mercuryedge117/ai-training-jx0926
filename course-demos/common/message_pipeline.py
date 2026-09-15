"""Transport-independent middleware, identity and command rules for L2."""
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic


class Pipeline:
    def __init__(self):
        self.middlewares = []

    def use(self, fn):
        self.middlewares.append(fn)
        return self

    def run(self, msg, handler):
        def dispatch(i, m):
            if i == len(self.middlewares):
                return handler(m)
            return self.middlewares[i](m, lambda m2: dispatch(i + 1, m2))
        return dispatch(0, msg)


def message_key(msg):
    return (msg['team_id'], msg['channel'], msg['ts'])


@dataclass
class Result:
    status: str
    reason: str | None
    event_id: str
    message_key: tuple | None = None
    reply_ts: str | None = None


def result(msg, status, reason=None, reply_ts=None):
    key = message_key(msg) if all(msg.get(k) for k in ('team_id', 'channel', 'ts')) else None
    return Result(status, reason, msg.get('event_id', ''), key, reply_ts)


def validate_message(msg, team, channel):
    if any(not isinstance(msg.get(k), str) or not msg[k]
           for k in ('event_id', 'team_id', 'channel', 'ts')):
        return 'invalid_envelope'
    if msg['team_id'] != team or msg['channel'] != channel:
        return 'outside_target_channel'
    if not re.fullmatch(r'\d+\.\d+', msg['ts']):
        return 'invalid_timestamp'
    if msg.get('event_type') not in ('message', 'app_mention'):
        return 'unsupported_event'
    if msg.get('subtype') not in (None, 'bot_message'):
        return 'unsupported_subtype'
    if not isinstance(msg.get('text'), str) or not msg['text'].strip():
        return 'empty_text'
    return None


def command(msg, bot_user):
    """Returns None for material, or explicit help/summary command tokens."""
    if msg.get('is_simulation'):
        return None
    if msg.get('event_type') != 'app_mention':
        return None
    text = re.sub(r'^\s*<@' + re.escape(bot_user) + r'>\s*', '', msg['text']).strip()
    parts = text.split()
    if parts == ['summary']:
        return ('summary', None)
    if len(parts) == 2 and parts[0] == 'summary' and parts[1] in ('engineer', 'manager'):
        return ('summary', parts[1])
    return ('help', None)


class SummaryRateLimit:
    """Only call on summary requests. Accepted failures still consume a slot."""
    def __init__(self, limit=3, window=60, clock=monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.requests = defaultdict(deque)

    def accept(self, msg):
        now = self.clock()
        key = (msg['team_id'], msg['channel'], msg['user_id'])
        times = self.requests[key]
        while times and now - times[0] >= self.window:
            times.popleft()
        if len(times) >= self.limit:
            return False
        times.append(now)
        return True
