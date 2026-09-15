"""Only this adapter imports Slack SDKs; offline processing never constructs them."""
import time


class SendFailure(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def post_message(client, **kwargs):
    """Retry only explicit 429 responses, never unknown send outcomes."""
    for attempt in range(2):
        try:
            response = client.chat_postMessage(**kwargs)
            if not response.get('ok'):
                raise SendFailure('slack_rejected')
            if not response.get('ts'):
                raise SendFailure('send_outcome_unknown')
            return response
        except SendFailure:
            raise
        except Exception as exc:
            response = getattr(exc, 'response', None)
            if response is not None and getattr(response, 'status_code', None) == 429 and attempt == 0:
                delay = float(response.headers.get('Retry-After', '1'))
                if 0 <= delay <= 30:
                    time.sleep(delay)
                    continue
            if response is not None:
                raise SendFailure('slack_rejected') from None
            raise SendFailure('send_outcome_unknown') from None


class ReplySender:
    def __init__(self, client):
        self.client = client

    def send_reply(self, channel, thread_ts, text):
        return post_message(self.client, channel=channel, thread_ts=thread_ts, text=text,
                            unfurl_links=False, unfurl_media=False)['ts']


class FakeClient:
    def __init__(self):
        self.posts = []

    def chat_postMessage(self, **kwargs):
        self.posts.append(kwargs)
        return {'ok': True, 'channel': kwargs['channel'], 'ts': f'9000000000.{len(self.posts):06d}'}


def connect(runtime, token, app_token, client):
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    # Local exception only: registry filtering in the runtime still rejects all
    # unregistered bot replies. The default SDK filter would hide our seed data.
    app = App(client=client, ignoring_self_events_enabled=False)

    @app.event('message')
    def on_message(body):
        runtime.ingest(body)

    @app.event('app_mention')
    def on_mention(body):
        runtime.ingest(body)

    handler = SocketModeHandler(app, app_token)
    handler.connect()
    return handler
