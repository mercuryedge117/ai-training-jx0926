# 第2课 · Slack API 集成

**演示要点**：本课两大企业级考察点——请求签名校验（安全）与 3 秒 ack + 异步处理（Slack 平台硬性限制）。

```bash
python verify_signature.py     # 演示签名计算/校验：合法、被篡改、过期三种case
python echo_server.py --test   # 用测试客户端向本地server发签名请求，观察ack与异步处理
python echo_server.py          # 真实运行（配合 ngrok 暴露给 Slack Events API）
python echo_server_ws.py --test # Socket Mode 离线自测，不访问 Slack
python echo_server_ws.py        # Socket Mode 真实运行，不需要公网 URL/ngrok
```

Socket Mode 运行前需要：

1. Slack App 后台开启 **Socket Mode**，App Token 带 `connections:write`
2. **Event Subscriptions** 订阅 bot events `app_mention` 和 `message.channels`
3. Bot Token Scopes 添加 `app_mentions:read`、`channels:history` 和 `chat:write`，改 scope 后重新安装 App
4. 设置 `SLACK_APP_TOKEN=xapp-...` 和 `SLACK_BOT_TOKEN=xoxb-...`，并把 bot 邀请进测试频道

`echo_server_ws.py` 会在原消息 thread 中回复 `echo: ...`。一次 @mention 会激活该 thread；脚本保持运行期间，bot 会继续 echo 该 thread 中的每条人类回复（不会回复自身或其他事件 subtype）。重启脚本后，需要再次 @mention 才会重新激活 thread。Socket Mode 不使用
`SLACK_SIGNING_SECRET`；该 secret 只用于 `echo_server.py` 的 HTTP 请求验签。

**面试预埋**："如何设计一个能应对第三方平台超时限制的异步架构？"——答案就在 `echo_server.py` 的 ack-then-process 模式里。
