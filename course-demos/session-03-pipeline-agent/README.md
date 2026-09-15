# L2 / L3 · Slack 消息 Pipeline Demo

普通讨论 → Pipeline → 本地记录 → `@bot summary` → 原 thread 摘要。普通消息不回复，Bot 的摘要不会再次进入材料。

## 先离线运行（不需要任何 token）

在仓库根目录执行：

```bash
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --offline
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --offline --scenario long
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --offline --scenario long --strategy map-reduce --chunk-tokens 2000
```

固定 fixture 随代码提供。离线模式强制 mock + FakeClient，即使 `.env` 配有真实 key 也不调用 Slack 或 LLM。mock 是基于实际输入的原文摘录，不能用于证明摘要语义正确。长素材是一条 Slack 消息，分块可以切进其正文。

也可以通过 `--manifest <path>` 回放旧发送清单；这验证业务链路，不代表真实 Slack 投递。

## 真实 Slack

安装 `course-demos/requirements.txt`，使用自己创建的 Python 虚拟环境；Windows 可用 `.venv/Scripts/python.exe`。共享 `.env` 放在 `course-demos/.env`，可从 `.env.example` 复制后填写。以下频道 ID 和 Bot 名称为讲师示例，请替换为自己的配置。

需要：Bot Token 的 `channels:history`、`app_mentions:read`、`chat:write`，以及本入口频道检查使用的 `channels:read`；App Token 的 `connections:write`。开启 Socket Mode，订阅 `message.channels` 和 `app_mention`，把 Bot 邀请进目标公开频道。

```bash
# 只监听，不自动发素材；模型强制 mock
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --socket --channel C0C16PDBFHR --mock

# 显式发送六条新模拟素材，真实事件到达后才入库
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --socket --channel C0C16PDBFHR --mock --seed short

# 把 short 换成 long 可发一条长素材。去掉 --mock 使用已配置模型。
```

监听就绪后，在频道发普通讨论，再用 Slack 提及选择器输入：

```text
@slack_assistant summary
@slack_assistant summary engineer
@slack_assistant summary manager
```

默认每次新建运行目录。`--store-dir <path>` 可重载某次记录；`--run-seconds 30` 可做限时接入验收。旧频道历史不会自动补回；命令只总结当前存储中的记录。

## 数据和结果

默认产物目录：`course-demos/outputs/slack-demo/<run-id>/`，已被 Git 忽略。

| 文件 | 内容 |
|---|---|
| `manifest.json` | seed 成功返回的实际消息 ts、正文、模拟角色 |
| `messages.jsonl` | 通过 Pipeline 的普通讨论和登记素材 |
| `trace.jsonl` | 放行、去重、拦截、失败原因和耗时 |
| `summary_runs.jsonl` | 摘要来源快照、模型/模式、正文及 Map 中间结果 |

`stored` 表示保存成功，`replied` 表示发送 API 返回成功。启动时既有记录不等于本次收到的新事件；观察 trace 的 `source=slack_live`。离线 source 为 `manifest_replay`/`fixture`。

## 中间件与课堂练习

`common/message_pipeline.py` 定义 `Pipeline`，入口组装日志 → 校验 → 来源过滤 → 去重 → 清洗 → 业务路由。日志包裹层在 `next_()` 返回后打印最终结果。

旧 L2 练习的 `rate_limit` 对所有消息限流；新 demo 的 `SummaryRateLimit`（摘要分支中的 `summary_rate_limit` 职责）只限制摘要请求：每 workspace/频道/用户滚动 60 秒最多 3 次。普通讨论照常保存，不能把旧全消息限流直接接到采集链。

模拟 Alice/Bob 共用 Bot 发送身份，角色保存在 `simulation_actor`；它们不执行命令、不消耗摘要请求配额。独立用户 fixture 验证限流隔离。

## 边界与排错

- SDK 的默认自消息过滤在此入口关闭，业务白名单仍只放行成功登记的当前 Bot 素材；不要把正文 `[模拟]` 当作可信凭据。
- 发帖返回之前到达的自消息暂存在有限 pending 缓冲；匹配返回 ts 后再入队。普通摘要回复不登记。
- 单 worker 与内存队列适合教学。队列满或 shutdown 未完成会报告覆盖不完整；不保证进程崩溃后恢复任务或恰好一次回帖。
- `--context-budget` 默认 32000，采用明确标记的保守 UTF-8 字节估计，并预留 1500 输出 token；应按实际模型设置。超预算报错，不静默丢材料。
- Map-Reduce 的 Reduce 也检查预算，超限明确失败并保存已产生的中间摘要。
- 回帖超时意味着结果未知，不自动重发。明确拒绝的回帖可在同进程显式重投原事件时复用缓存摘要；没有对外的自动重试服务。
- `posted > stored`：检查后台订阅、是否有另一个进程连接同一 App、pending/queue 错误和 trace。生成器绝不直接写消息存储。
- 普通中文演示使用 UTF-8 输出。损坏 JSONL 会指出行号，修复后再重启。

## 保留的基础示例

```bash
python course-demos/session-03-pipeline-agent/pipeline.py
python course-demos/session-03-pipeline-agent/chat_agent.py
python course-demos/session-04-summarization/summarize.py --chunk-size 6
```

最后一条是原 L3 按消息条数强制分块的教学入口；新 demo 使用独立的文本预算。真实模型仍通过 `common/llm.py` 统一调用。

## 测试

```bash
python -m pytest -q course-demos/tests/test_pipeline_demo.py
python -m pytest -q
```

设计依据：[Review spec](PIPELINE_DEMO_SPEC.md)。实时验证记录见 [验收记录](DEMO_VALIDATION.md)。
