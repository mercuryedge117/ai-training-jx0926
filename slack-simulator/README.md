# Slack Team Simulator

模拟一个 8 人研发小组（CloudCart 支付团队）的日常 Slack 工作流，为 AI SlackBot 实战营提供教学数据。覆盖三条业务线：**项目开发**（sprint/standup/PR review）、**客户请求**（工单升级/FAQ/功能需求）、**线上事故**（告警/war room/postmortem）。

## 目录结构

```
slack-simulator/
├── config/
│   ├── personas.yaml              # 8个成员角色卡 + 频道定义
│   ├── tokens.yaml                # (可选) 每成员独立bot token
│   └── scenarios/
│       ├── incident_payment_outage.yaml   # 事故线（完整）
│       ├── dev_sprint.yaml                # 开发线
│       └── customer_request.yaml          # 客户请求线
├── data/
│   ├── sample_messages.jsonl      # 预生成的55条消息，无需API key即可注入
│   └── ground_truth.json          # 评分标注：行动项/风险/摘要要点/FAQ
├── kb/                            # RAG知识库文档（3篇）
├── generate_messages.py           # LLM按剧本生成新消息
└── inject_slack.py                # 注入Slack（batch/realtime/dry-run）
```

## 快速开始（10分钟）

**1. 建 Slack 环境**：创建免费 workspace → https://api.slack.com/apps 建一个 App → Bot Token Scopes 添加 `chat:write`, `chat:write.customize`, `channels:manage`, `channels:read`, `channels:join` → Install to Workspace → 复制 `xoxb-` token。

**2. 安装依赖**：`pip install slack_sdk pyyaml`

**3. 预览（不需要token）**：
```bash
python inject_slack.py data/sample_messages.jsonl --dry-run
```

**4. 注入**：
```bash
export SLACK_BOT_TOKEN=xoxb-...
python inject_slack.py data/sample_messages.jsonl            # 批量灌历史
python inject_slack.py data/sample_messages.jsonl --realtime --speed 60   # 实时回放演示
```

脚本会自动创建缺失的频道。消息以成员显示名发出（`chat:write.customize`），若 workspace 不允许则自动降级为 `*Sarah Chen:* ...` 前缀模式。

## 生成新剧情（需要 LLM key）

```bash
export OPENAI_API_KEY=sk-...        # 或 ANTHROPIC_API_KEY
python generate_messages.py config/scenarios/dev_sprint.yaml
python inject_slack.py data/generated_messages.jsonl
```

剧本采用「事件骨架 + LLM填充」模式：YAML 里每个 event 定义时间/频道/参与者/剧情要点/ground truth，LLM 只负责把要点扩写成 3-8 条符合角色语气的消息。写新剧本 = 复制一个 YAML 改事件列表。

## Ground Truth 与教学评分

`data/ground_truth.json` 与 sample 消息逐条对齐（`source_messages` 指向消息id），包含四类标注，对应课程各模块的评分基准：

| 标注 | 数量 | 用于评估 |
|---|---|---|
| action_items | 15条（含owner/due/priority） | 模块3 任务提取 |
| risk_alerts | 2条（high/medium） | 模块4 风险预警 |
| summaries | 2个窗口的must_include要点 | 模块2 摘要质量 |
| faq | 4条标准问答 | 模块4 RAG问答 |

学员 bot 的输出直接和这份标注对比即可算准确率/召回率。`kb/` 下 3 篇文档（runbook、webhook FAQ、事故规范）供 RAG 模块建索引，FAQ 答案均可在其中溯源。

## 每期开营重置

新建频道或 archive 旧频道后重跑注入脚本即可，约10分钟。同一份 JSONL 可重复灌入任何 workspace。

## 测试

```bash
pip install -r requirements.txt pytest
pytest tests/ -v            # 或在仓库根目录跑 `pytest`，会连同 course-demos/tests 一起执行
```

覆盖 `load_messages`/`load_personas`（数据加载与排序）、`--dry-run` 注入路径、`generate_messages.py` 的纯逻辑部分（JSON 解析、人设拼装）——都不需要 Slack token 或 LLM key。

## 已知限制

- Slack API 不能伪造消息时间戳：批量注入的消息时间是注入时刻，剧情时间保存在 `sim_ts` 字段（学员 bot 应以文本和 `sim_ts` 为准，或使用 realtime 模式贴近真实时序）。
- 免费版 Slack 仅保留 90 天历史，对单期教学足够。
- 单 token 模式下所有消息实际来自同一个 bot（显示名不同）；如需真实的多用户 user id（例如练习 @mention 解析），为每个成员建独立 App 并填入 `config/tokens.yaml`。
