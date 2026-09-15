import json
import socket
from pathlib import Path
from threading import Event

import pytest
from conftest import load_session
from common.message_store import MessageStore
from common.summarization import summarize, BudgetExceeded
from common import llm

demo = load_session('session-03-pipeline-agent', 'slack_pipeline_demo')


def body(ts='100.000001', *, text='正常讨论', user='U1', kind='message', **fields):
    return {'event_id': 'Ev' + ts, 'team_id': 'T1',
            'event': {'type': kind, 'channel': 'C1', 'ts': ts, 'user': user, 'text': text, **fields}}


@pytest.fixture
def runtime(tmp_path):
    client = demo.FakeClient()
    obj = demo.DemoRuntime(tmp_path, 'T1', 'C1', 'UBOT', 'BBOT', demo.ReplySender(client))
    obj.client = client
    yield obj
    obj.close()


def send(runtime, event):
    runtime.ingest(event, 'fixture')
    assert runtime.wait_idle()
    return runtime.results[-1]


def ask(ts='101.000001', user='U1', **fields):
    return body(ts, kind='app_mention', user=user, text='<@UBOT> summary', **fields)


def test_full_record_summary_thread_and_dedupe(runtime):
    first = body(text='  支付故障已恢复，根因尚未确认。  ')
    assert send(runtime, first)['status'] == 'stored'
    assert runtime.client.posts == []
    assert send(runtime, first)['status'] == 'duplicate'
    first['event_id'] = 'DifferentDelivery'
    assert send(runtime, first)['status'] == 'duplicate'
    assert send(runtime, ask(thread_ts='90.000001'))['status'] == 'replied'
    assert runtime.client.posts[0]['thread_ts'] == '90.000001'
    assert '根因尚未确认' in runtime.client.posts[0]['text']
    assert len(runtime.store.messages) == 1
    assert len(MessageStore(runtime.folder/'messages.jsonl').messages) == 1
    assert runtime.store.snapshot('T1', 'C1')[0]['text'].startswith('支付')


def test_source_identity_and_bot_loop(runtime):
    assert send(runtime, body(user=None))['reason'] == 'missing_user_id'
    assert send(runtime, body(bot_id='OTHER'))['reason'] == 'unregistered_bot'
    assert send(runtime, body(user='UBOT', bot_id='BBOT'))['reason'] == 'unregistered_bot'
    assert send(runtime, body(channel='C2'))['reason'] == 'outside_target_channel'
    assert send(runtime, body(subtype='message_changed'))['reason'] == 'unsupported_subtype'
    assert send(runtime, body(text='[模拟] 普通用户标签'))['status'] == 'stored'
    assert not runtime.store.snapshot('T1', 'C1')[0].get('is_simulation')
    for i, actor in enumerate(['Alice', 'Bob'], 2):
        ts = f'100.{i:06d}'
        runtime.registry.register('T1', 'C1', ts, actor, 'run')
        assert send(runtime, body(ts, user=None, bot_id='BBOT', text='<@UBOT> summary'))['status'] == 'stored'
    records = runtime.store.snapshot('T1', 'C1')[1:]
    assert [m['user_id'] for m in records] == ['UBOT', 'UBOT']
    assert [m['simulation_actor'] for m in records] == ['Alice', 'Bob']
    assert not runtime.client.posts


def test_dual_listener_command_not_material(runtime):
    assert send(runtime, body(text='<@UBOT> summary'))['reason'] == 'mention_owned_by_command_listener'
    assert send(runtime, ask('100.000001'))['status'] == 'replied'
    assert not runtime.store.messages
    assert '尚无' in runtime.client.posts[0]['text']


def test_summary_rate_limit_boundary_and_users(runtime):
    now = [0.0]
    runtime.limiter.clock = lambda: now[0]
    send(runtime, body())
    for i in range(3):
        assert send(runtime, ask(f'101.{i:06d}'))['status'] == 'replied'
    assert send(runtime, ask('102.000001'))['status'] == 'rate_limited'
    assert send(runtime, ask('102.000002', user='U2'))['status'] == 'replied'
    assert send(runtime, body('103.000001'))['status'] == 'stored'
    now[0] = 60
    assert send(runtime, ask('104.000001'))['status'] == 'replied'


def test_seed_receipt_race_and_timeout(runtime):
    reg = runtime.registry
    reg.active = True
    event = body(user='UBOT', bot_id='BBOT')
    runtime.ingest(event)
    assert len(reg.pending) == 1 and not runtime.store.messages
    reg.register('T1', 'C1', '100.000001', 'Alice', 'run')
    assert runtime.wait_idle()
    assert len(runtime.store.messages) == 1
    runtime.ingest(body('100.000002', user='UBOT', bot_id='BBOT'))
    reg.expire(force=True)
    assert runtime.results[-1]['reason'] == 'seed_receipt_timeout'
    assert len(runtime.store.messages) == 1


def test_slow_model_does_not_block_ingress(runtime):
    entered, release = Event(), Event()
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return {'text': 'summary', 'mode': 'mock'}
    send(runtime, body())
    runtime.summarizer = slow
    runtime.ingest(ask())
    assert entered.wait(1)
    try:
        runtime.ingest(body('102.000001'))
        assert runtime.queue.qsize() == 1
    finally:
        release.set()
    assert runtime.wait_idle()
    assert len(runtime.store.messages) == 2


def test_queue_full(tmp_path):
    obj = demo.DemoRuntime(tmp_path, 'T1', 'C1', 'UBOT', 'BBOT', demo.ReplySender(demo.FakeClient()),
                           start=False, queue_size=1)
    obj.ingest(body())
    result = obj.ingest(body('100.000002'))
    assert result.reason == 'queue_full' and obj.incomplete
    obj.worker.start()
    assert obj.wait_idle()
    obj.close()


def test_storage_and_model_failure_retry(runtime, monkeypatch):
    original = runtime.store.append_if_absent
    def fail(*args, **kwargs):
        raise OSError('not exposed')
    monkeypatch.setattr(runtime.store, 'append_if_absent', fail)
    assert send(runtime, body())['reason'] == 'storage_failed'
    monkeypatch.setattr(runtime.store, 'append_if_absent', original)
    assert send(runtime, body())['status'] == 'stored'
    runtime.summarizer = fail
    assert send(runtime, ask())['reason'] == 'summary_failed'
    assert len(runtime.limiter.requests[('T1','C1','U1')]) == 1
    runtime.summarizer = summarize
    assert send(runtime, ask())['status'] == 'replied'
    assert len(runtime.limiter.requests[('T1','C1','U1')]) == 1


def test_failed_post_reuses_summary_and_unknown_does_not_resend(runtime):
    from slack_adapter import SendFailure
    send(runtime, body())
    calls = []
    runtime.summarizer = lambda *a, **kw: calls.append(1) or {'text':'retained','mode':'mock'}
    original = runtime.sender.send_reply
    def fail(*args):
        raise SendFailure('slack_rejected')
    runtime.sender.send_reply = fail
    assert send(runtime, ask())['reason'] == 'slack_rejected'
    runtime.sender.send_reply = original
    assert send(runtime, ask())['status'] == 'replied' and len(calls) == 1
    def unknown(*args):
        raise TimeoutError()
    runtime.sender.send_reply = unknown
    assert send(runtime, ask('102.000001'))['reason'] == 'send_outcome_unknown'
    runtime.sender.send_reply = original
    assert send(runtime, ask('102.000001'))['reason'] == 'send_outcome_unknown_manual_check_required'


def test_offline_with_keys_cannot_call_network(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-do-not-use')
    def forbidden(*args, **kwargs):
        pytest.fail('offline attempted network')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(llm, 'call_llm', forbidden)
    monkeypatch.setattr('sys.argv', ['demo', '--offline', '--store-dir', str(tmp_path)])
    assert demo.main() == 0
    assert len(MessageStore(tmp_path/'messages.jsonl').messages) == 6


def test_long_fixture_and_budget(tmp_path):
    from demo_fixtures import load_manifest
    data = load_manifest(scenario='long')
    rows = [{'text':r['text'], 'ts':r['ts'], 'user_id':'demo:bot'} for r in data['messages']]
    assert len(rows) == 1
    with pytest.raises(BudgetExceeded):
        summarize(rows, mock=True, context_budget=2000)
    output = summarize(rows, mock=True, strategy='map-reduce', chunk_tokens=2000)
    assert len(output['partials']) > 1
    assert all(p['source'] == output['partials'][0]['source'] for p in output['partials'])
    assert 'mock' in output['text']


def test_jsonl_corruption_is_not_silently_ignored(tmp_path):
    path = tmp_path/'messages.jsonl'
    path.write_text('{bad', encoding='utf-8')
    with pytest.raises(ValueError, match='messages.jsonl:1'):
        MessageStore(path)


def test_reduce_overflow_preserves_map_evidence():
    messages = [{'text': 'many facts ' * 1000, 'ts': '100.000001', 'user_id': 'U1'}]
    with pytest.raises(BudgetExceeded) as error:
        summarize(messages, mock=True, strategy='map-reduce', context_budget=4000, chunk_tokens=1000)
    assert len(error.value.partials) > 1
    assert all(p['source'] for p in error.value.partials)


def test_seed_uses_events_not_direct_store(runtime, monkeypatch):
    seed_module = load_session('session-03-pipeline-agent', 'seed_demo')
    monkeypatch.setattr(seed_module.time, 'sleep', lambda _: None)
    count = [0]
    class EchoingSlack:
        def chat_postMessage(self, **kwargs):
            count[0] += 1
            ts = f'200.{count[0]:06d}'
            # Delivery beats the response: exercises pending registration path.
            runtime.ingest(body(ts, user='UBOT', bot_id='BBOT', text=kwargs['text']))
            return {'ok': True, 'ts': ts, 'channel': kwargs['channel']}
    assert seed_module.seed(EchoingSlack(), runtime.registry, 'T1', 'C1', 'seed-run', runtime.folder) == 6
    assert runtime.wait_idle()
    assert len(runtime.store.messages) == 6
    assert all(row['source'] == 'slack_live' for row in runtime.store.messages.values())
    manifest = json.loads((runtime.folder/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['messages']) == 6


def test_seed_without_events_cannot_claim_collection(runtime, monkeypatch):
    seed_module = load_session('session-03-pipeline-agent', 'seed_demo')
    monkeypatch.setattr(seed_module.time, 'sleep', lambda _: None)
    assert seed_module.seed(demo.FakeClient(), runtime.registry, 'T1', 'C1', 'seed-run', runtime.folder) == 6
    assert not runtime.store.messages
    runtime.close()
    assert runtime.incomplete
