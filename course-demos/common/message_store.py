"""Single-writer JSONL store. No claim of durable task/exactly-once delivery."""
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from threading import Lock

from .message_pipeline import message_key


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def read(self):
        if not self.path.exists():
            return []
        rows = []
        for number, line in enumerate(self.path.read_text(encoding='utf-8').splitlines(), 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('expected object')
                rows.append(row)
            except (ValueError, TypeError) as exc:
                raise ValueError(f'{self.path.name}:{number}: invalid JSONL; repair this line before restarting') from exc
        return rows

    def append(self, row):
        data = json.dumps(row, ensure_ascii=False) + '\n'
        with self.lock, self.path.open('a', encoding='utf-8') as stream:
            stream.write(data)
            stream.flush()


class MessageStore:
    def __init__(self, path):
        self.journal = Journal(path)
        self.messages = {}
        for row in self.journal.read():
            self.messages[message_key(row)] = row

    def append_if_absent(self, message):
        key = message_key(message)
        if key in self.messages:
            return False
        row = deepcopy(message)
        self.journal.append(row)  # Only mark complete after a successful write.
        self.messages[key] = row
        return True

    def snapshot(self, team, channel):
        rows = [m for m in self.messages.values()
                if m['team_id'] == team and m['channel'] == channel]
        rows.sort(key=lambda m: Decimal(m['ts']))
        return deepcopy(rows)
