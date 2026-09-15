# AI Training

企业级 AI 应用训练课程：从项目环境、Slack 数据、LLM 调用入口开始，逐步扩展到消息处理、摘要、任务提取、RAG、风险分析、编排集成与评分。

当前仓库已发布 L1–L3 所需代码、L2/L3 教案及练习模板。完整课程架构见 [course-demos/ARCHITECTURE.md](course-demos/ARCHITECTURE.md)。

## 通用准备

建议使用 Python 3.12。每个 session 的具体运行命令请进入对应目录查看说明。

如需配置本地密钥，复制 `course-demos/.env.example` 为 `course-demos/.env`，再填入自己的 Slack 或 LLM 密钥。不要提交 `.env`。

在仓库根目录安装依赖：

```bash
python -m pip install -r course-demos/requirements.txt
```

L2/L3 离线入口不需要密钥；真实模型沿用共享配置，使用 Anthropic 时另安装 `anthropic`。课件中的频道 ID 和 Bot 名称是讲师环境示例，真实接入时替换为自己的测试频道与 Bot。

## GitHub authentication

学生需要先完成 GitHub 认证，才能从私有仓库 clone/pull/push。最常见、也最省心的方法是 GitHub CLI；GitHub 官方也推荐用 GitHub CLI 或 Git Credential Manager 来缓存 HTTPS 凭据。

### Windows (PowerShell)

推荐方式：安装 Git for Windows 和 GitHub CLI，然后登录：

```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
gh auth login
gh auth setup-git
gh auth status
```

`gh auth login` 过程中选择：

- `GitHub.com`
- `HTTPS`
- `Y`，允许 GitHub CLI 认证 Git 操作
- 按提示在浏览器完成登录

备选方式：只安装最新版 Git for Windows。它自带 Git Credential Manager；第一次 clone/pull/push HTTPS 仓库时，会自动弹出浏览器登录。

### macOS (Terminal)

推荐方式：用 Homebrew 安装 GitHub CLI，然后登录：

```bash
brew install gh
gh auth login
gh auth setup-git
gh auth status
```

`gh auth login` 过程中选择：

- `GitHub.com`
- `HTTPS`
- `Y`，允许 GitHub CLI 认证 Git 操作
- 按提示在浏览器完成登录

备选方式：使用 Git Credential Manager：

```bash
brew install git
brew install --cask git-credential-manager
```

之后第一次 clone/pull/push HTTPS 仓库时，会通过浏览器完成 GitHub 登录，并把凭据保存在 macOS Keychain。

## Sessions

- [Session 1: 环境搭建、Hello Bot、统一 LLM 调用入口与诗词机器人架构练习](course-demos/session-01-setup/README.md)
- [L2：Slack 接入与消息管道教案](教案_4周9次课/L2_Slack接入与消息管道.md)
- [L3：LLM 摘要与长文本教案](教案_4周9次课/L3_LLM摘要与长文本.md)
- [L2/L3 集成 Demo：运行说明](course-demos/session-03-pipeline-agent/README.md) · [设计](course-demos/session-03-pipeline-agent/PIPELINE_DEMO_SPEC.md)

保留原代码目录编号以兼容课件命令：L2 使用 `session-02-slack-api` 和 `session-03-pipeline-agent`；L3 使用该 Pipeline 及 `session-04-summarization`，目录编号不等于当前课次编号。[总览与排课](教案_4周9次课/00_总览与排课.md) 包含后续课程计划，本次只补充 L2/L3。

从仓库根目录运行离线演示与测试：

```bash
python course-demos/session-02-slack-api/verify_signature.py
python course-demos/session-02-slack-api/echo_server.py --test
python course-demos/session-02-slack-api/echo_server_ws.py --test
python course-demos/session-03-pipeline-agent/pipeline.py
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --offline
python course-demos/session-03-pipeline-agent/slack_pipeline_demo.py --offline --scenario long --strategy map-reduce --chunk-tokens 2000
python -m pytest -q
```

离线 Pipeline 强制 mock，只验证消息处理与摘要流程。运行日志保存在 `course-demos/outputs/`，不提交到仓库；真实模型质量需要另行对照原文检查。

## Practices

- [Session 1：诗词聊天机器人](course-demos/session-01-setup/practices/session-01-poem-bot.md)
- [L3：同一快照，两类读者](course-demos/session-03-pipeline-agent/practices/summary_two_audiences.md)
- [L3：单次摘要与分块对照](course-demos/session-03-pipeline-agent/practices/chunk_comparison.md)
