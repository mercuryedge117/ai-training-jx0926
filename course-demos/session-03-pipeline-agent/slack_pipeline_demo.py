"""L2/L3: events -> middleware -> stored conversation -> on-demand summary."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from queue import Queue, Empty, Full
import sys
from threading import Event, Thread, Lock
from time import monotonic
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.message_pipeline import Pipeline, SummaryRateLimit, command, message_key, result, validate_message
from common.message_store import Journal, MessageStore
from common.summarization import summarize, BudgetExceeded
from demo_fixtures import DemoRegistry, load_manifest, replay_events, summary_event
from slack_adapter import FakeClient, ReplySender, SendFailure


class DemoRuntime:
    def __init__(self, folder, team, channel, bot_user, bot_id, sender, *,
                 mock=True, audience='engineer', strategy='single', registry=None,
                 summarizer=summarize, clock=monotonic, queue_size=100,
                 context_budget=32000, chunk_tokens=4000, start=True):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.team, self.channel = team, channel
        self.bot_user, self.bot_id, self.sender = bot_user, bot_id, sender
        self.mock, self.audience, self.strategy = mock, audience, strategy
        self.context_budget, self.chunk_tokens = context_budget, chunk_tokens
        self.summarizer = summarizer
        self.registry = registry or DemoRegistry()
        self.store = MessageStore(self.folder / 'messages.jsonl')
        self.trace = Journal(self.folder / 'trace.jsonl')
        self.summaries = Journal(self.folder / 'summary_runs.jsonl')
        self.limiter = SummaryRateLimit(clock=clock)
        self.queue = Queue(maxsize=queue_size)
        self.stop = Event()
        self.ingress_lock = Lock()
        self.accepting = True
        self.done_events, self.done_messages = set(), set()
        self.inflight = set()
        self.cache, self.accepted_commands, self.unknown_sends = {}, set(), set()
        self.results = []
        self.incomplete = False
        self.registry.on_ready = self.enqueue
        self.registry.on_expired = self.expired_seed
        self.pipe = (Pipeline().use(self.audit).use(self.validate).use(self.source_filter)
                     .use(self.dedupe).use(self.normalize))
        self.worker = Thread(target=self.work, name='l2-pipeline-worker', daemon=True)
        if start:
            self.worker.start()

    def record(self, msg, outcome, elapsed=0):
        row = {**asdict(outcome), 'source': msg.get('source'), 'elapsed_ms': round(elapsed * 1000, 2)}
        self.trace.append(row)
        self.results.append(row)
        print(f"{outcome.event_id} -> {outcome.status}:{outcome.reason or '-'}", file=sys.stderr)
        return outcome

    def expired_seed(self, msg):
        self.incomplete = True
        self.record(msg, result(msg, 'ignored', 'seed_receipt_timeout'))

    def is_self(self, msg):
        if msg.get('bot_id'):
            return msg['bot_id'] == self.bot_id
        return msg.get('user_id') == self.bot_user

    def ingest(self, body, source='slack_live'):
        event = body.get('event', {})
        if not isinstance(event, dict):
            event = {}
        msg = {'event_id': body.get('event_id'), 'team_id': body.get('team_id'),
               'channel': event.get('channel'), 'ts': event.get('ts'),
               'thread_ts': event.get('thread_ts'), 'user_id': event.get('user'),
               'bot_id': event.get('bot_id'), 'event_type': event.get('type'),
               'subtype': event.get('subtype'), 'text': event.get('text'), 'source': source,
               'demo_run_id': None, 'simulation_actor': None}
        reason = validate_message(msg, self.team, self.channel)
        if reason:
            return self.record(msg, result(msg, 'ignored', reason))
        # Only own bot messages in an active seed can await an API receipt.
        if self.is_self(msg) and not self.registry.lookup(message_key(msg)):
            disposition = self.registry.defer(msg)
            if disposition == 'pending':
                return None
            if disposition == 'rejected':
                return self.record(msg, result(msg, 'ignored', 'unregistered_bot'))
        return self.enqueue(msg)

    def enqueue(self, msg):
        with self.ingress_lock:
            if not self.accepting:
                self.incomplete = True
                return self.record(msg, result(msg, 'failed', 'shutting_down'))
            try:
                self.queue.put_nowait(msg)
            except Full:
                self.incomplete = True
                return self.record(msg, result(msg, 'failed', 'queue_full'))
        return None

    def work(self):
        while not self.stop.is_set() or not self.queue.empty():
            self.registry.expire()
            try:
                msg = self.queue.get(timeout=.1)
            except Empty:
                continue
            try:
                self.pipe.run(msg, self.route)
            except Exception:
                # A journal write can fail too. Preserve liveness and report no success.
                self.incomplete = True
                print('worker failed: audit/storage unavailable', file=sys.stderr)
            finally:
                self.queue.task_done()

    def wait_idle(self, timeout=10):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            with self.queue.all_tasks_done:
                if not self.queue.unfinished_tasks:
                    return True
                self.queue.all_tasks_done.wait(min(.1, max(0, deadline - monotonic())))
        return False

    def close(self, timeout=5):
        with self.ingress_lock:
            self.accepting = False
        self.registry.expire(force=True)
        self.stop.set()
        if self.worker.is_alive():
            self.worker.join(timeout)
        if self.queue.unfinished_tasks:
            self.incomplete = True
            print(f'Incomplete shutdown: {self.queue.unfinished_tasks} unfinished', file=sys.stderr)
        missing = set(self.registry.entries) - set(self.store.messages)
        if missing:
            self.incomplete = True
            print(f'Incomplete seed coverage: {len(missing)} registered messages not stored', file=sys.stderr)

    def audit(self, msg, next_):
        begin = monotonic()
        try:
            outcome = next_(msg)
        except Exception as exc:
            outcome = result(msg, 'failed', 'internal_' + type(exc).__name__)
        return self.record(msg, outcome, monotonic() - begin)

    def validate(self, msg, next_):
        reason = validate_message(msg, self.team, self.channel)
        return result(msg, 'ignored', reason) if reason else next_(msg)

    def source_filter(self, msg, next_):
        is_bot = bool(msg.get('bot_id') or msg.get('subtype') == 'bot_message' or self.is_self(msg))
        if is_bot:
            entry = self.registry.lookup(message_key(msg))
            if not self.is_self(msg) or entry is None:
                return result(msg, 'ignored', 'unregistered_bot')
            msg = {**msg, **entry, 'is_simulation': True,
                   'user_id': msg.get('user_id') or self.bot_user}
            if msg['user_id'] != self.bot_user:
                return result(msg, 'ignored', 'bot_identity_mismatch')
        if not isinstance(msg.get('user_id'), str) or not msg['user_id']:
            return result(msg, 'ignored', 'missing_user_id')
        if (not msg.get('is_simulation') and msg['event_type'] == 'message'
                and f'<@{self.bot_user}>' in msg['text']):
            return result(msg, 'ignored', 'mention_owned_by_command_listener')
        return next_(msg)

    def dedupe(self, msg, next_):
        key, eid = message_key(msg), msg['event_id']
        if eid in self.done_events or key in self.done_messages or key in self.inflight:
            return result(msg, 'duplicate', 'already_processed')
        if key in self.unknown_sends:
            return result(msg, 'failed', 'send_outcome_unknown_manual_check_required')
        self.inflight.add(key)
        try:
            outcome = next_(msg)
            if outcome.status in ('stored', 'replied', 'duplicate', 'rate_limited'):
                self.done_events.add(eid)
                self.done_messages.add(key)
            return outcome
        finally:
            self.inflight.discard(key)

    def normalize(self, msg, next_):
        return next_({**msg, 'text': msg['text'].strip()})

    def reply(self, msg, text, status='replied', reason=None):
        if len(text) > 3000:
            text = text[:2900] + '\n[预览已截取；完整结果保存于 summary_runs.jsonl]'
        try:
            ts = self.sender.send_reply(msg['channel'], msg.get('thread_ts') or msg['ts'], text)
            return result(msg, status, reason, ts)
        except SendFailure as exc:
            if exc.reason == 'send_outcome_unknown':
                self.unknown_sends.add(message_key(msg))
            return result(msg, 'failed', exc.reason)
        except Exception:
            self.unknown_sends.add(message_key(msg))
            return result(msg, 'failed', 'send_outcome_unknown')

    def route(self, msg):
        cmd = command(msg, self.bot_user)
        if cmd is None:
            try:
                stored = self.store.append_if_absent(msg)
            except Exception:
                self.incomplete = True
                return result(msg, 'failed', 'storage_failed')
            return result(msg, 'stored' if stored else 'duplicate', None if stored else 'message_key')
        if cmd[0] == 'help':
            return self.reply(msg, '使用：@bot summary [engineer|manager]。只总结本地已收集的记录。')
        key = message_key(msg)
        if key not in self.accepted_commands:
            if not self.limiter.accept(msg):
                return self.reply(msg, '摘要请求过多：每位用户每频道 60 秒最多 3 次。', 'rate_limited', 'summary_request')
            self.accepted_commands.add(key)
        if key not in self.cache:
            snapshot = self.store.snapshot(msg['team_id'], msg['channel'])
            if not snapshot:
                return self.reply(msg, '尚无已收集的消息，请先在本频道讨论。')
            keys = [message_key(m) for m in snapshot]
            try:
                summary = self.summarizer(snapshot, audience=cmd[1] or self.audience,
                                          strategy=self.strategy, mock=self.mock,
                                          context_budget=self.context_budget, chunk_tokens=self.chunk_tokens)
            except Exception as exc:
                reason = 'budget_exceeded' if isinstance(exc, BudgetExceeded) else 'summary_failed'
                self.summaries.append({'event_id': msg['event_id'], 'message_keys': keys, 'error': reason,
                                       'partials': getattr(exc, 'partials', [])})
                return self.reply(msg, f'摘要失败（{reason}）；原消息仍保留，可缩小范围后重新请求。', 'failed', reason)
            period = f"{snapshot[0]['ts']} — {snapshot[-1]['ts']} (Slack ts)"
            header = f"[{summary['mode']}] 已收集 {len(snapshot)} 条；范围 {period}"
            if self.incomplete:
                header += '\n注意：本次收集存在失败，覆盖不完整。'
            text = header + '\n' + summary['text']
            self.summaries.append({'event_id': msg['event_id'], 'message_keys': keys,
                                   'sources': sorted({m['source'] for m in snapshot}),
                                   'range': period, 'reply_text': text, **summary})
            self.cache[key] = text
        return self.reply(msg, self.cache[key])


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    modes = ap.add_mutually_exclusive_group(required=True)
    modes.add_argument('--offline', action='store_true')
    modes.add_argument('--socket', action='store_true')
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--scenario', choices=['short', 'long'], default='short')
    ap.add_argument('--channel')
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--seed', choices=['short', 'long'])
    ap.add_argument('--store-dir', type=Path)
    ap.add_argument('--audience', choices=['engineer', 'manager'], default='engineer')
    ap.add_argument('--strategy', choices=['single', 'map-reduce'], default='single')
    ap.add_argument('--context-budget', type=int, default=32000,
                    help='configured model budget; conservative UTF-8 byte estimate')
    ap.add_argument('--chunk-tokens', type=int, default=4000)
    ap.add_argument('--run-seconds', type=float, help='bounded live acceptance run')
    args = ap.parse_args()
    if args.socket and (not args.channel or args.manifest):
        ap.error('--socket requires --channel and does not import manifests')
    if args.offline and args.seed:
        ap.error('--seed requires --socket')
    if args.context_budget <= 1500 or args.chunk_tokens < 1:
        ap.error('invalid token budget')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    folder = args.store_dir or Path(__file__).resolve().parents[1] / 'outputs' / 'slack-demo' / run_id
    if args.offline:
        manifest = load_manifest(args.manifest, args.scenario)
        client = FakeClient()
        runtime = DemoRuntime(folder, 'demo:manifest', manifest['channel_id'], 'demo:bot',
                              'demo:bot-id', ReplySender(client), audience=args.audience,
                              strategy=args.strategy, context_budget=args.context_budget, chunk_tokens=args.chunk_tokens)
        try:
            for body in replay_events(manifest, runtime.registry):
                runtime.ingest(body, 'manifest_replay')
            runtime.ingest(summary_event(manifest['channel_id'], audience=args.audience), 'fixture')
            if not runtime.wait_idle(30):
                raise RuntimeError('offline worker did not finish')
            for post in client.posts:
                print(post['text'])
            print(f'Artifacts: {folder}')
            if runtime.incomplete or any(r['status'] == 'failed' for r in runtime.results):
                return 1
            return 0
        finally:
            runtime.close()
    # SDK imports and credentials are only used in live mode.
    from dotenv import load_dotenv
    from slack_sdk import WebClient
    from slack_adapter import connect
    from seed_demo import seed
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    token, app_token = os.getenv('SLACK_BOT_TOKEN'), os.getenv('SLACK_APP_TOKEN')
    if not token or not app_token:
        raise ValueError('Socket mode requires SLACK_BOT_TOKEN and SLACK_APP_TOKEN')
    client = WebClient(token=token, timeout=20, retry_handlers=[])
    auth = client.auth_test()
    info = client.conversations_info(channel=args.channel)['channel']
    if info.get('is_private') or not info.get('is_member'):
        raise ValueError('Target must be a public channel containing this bot')
    runtime = DemoRuntime(folder, auth['team_id'], args.channel, auth['user_id'], auth['bot_id'],
                          ReplySender(client), mock=args.mock, audience=args.audience,
                          strategy=args.strategy, context_budget=args.context_budget, chunk_tokens=args.chunk_tokens)
    handler = None
    try:
        handler = connect(runtime, token, app_token, client)
        print(f'Connected: {args.channel}. Event subscriptions must include message.channels and app_mention.', flush=True)
        if args.seed:
            posted = seed(client, runtime.registry, auth['team_id'], args.channel, run_id, folder, args.seed)
            print(f'posted={posted}; awaiting real Slack events (no direct store writes)')
        deadline = monotonic() + args.run_seconds if args.run_seconds is not None else None
        while deadline is None or monotonic() < deadline:
            runtime.stop.wait(.2)
    except KeyboardInterrupt:
        pass
    finally:
        if handler:
            handler.close()
        runtime.close()
        print(f"stored={len(runtime.store.messages)}; coverage_incomplete={runtime.incomplete}; artifacts={folder}")
    return 1 if runtime.incomplete else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # SDK exception strings can include request/response details. Keep secrets out.
        print(f'Demo stopped: {type(exc).__name__}. Check configuration and trace files.', file=sys.stderr)
        raise SystemExit(1)
