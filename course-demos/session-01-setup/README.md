# 第1课 · 环境搭建

**演示要点**：企业级项目从环境自检开始——依赖、密钥、连通性都应可一键验证，而不是"在我机器上能跑"。

开始前请先按根目录 [README.md](../../README.md) 的 GitHub authentication 部分完成 GitHub 登录；Windows/macOS 最常见方式都是使用 GitHub CLI 的 `gh auth login`，也可以使用 Git Credential Manager。

建议使用 Python 3.12。没有 Slack token 时，Hello Bot 使用控制台模式；输入 quit 退出。可选模型 SDK 或密钥显示 MISSING 不影响离线练习。

如需配置本地密钥，复制 `../.env.example` 为 `../.env`，再填入自己的 Slack 或 LLM 密钥。不要提交 `.env`。

## Quick start

### Windows (PowerShell)

从仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r course-demos/requirements.txt
python course-demos/session-01-setup/check_env.py
python course-demos/session-01-setup/hello_bot.py
python -m pytest -q
```

### macOS (Terminal)

从仓库根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r course-demos/requirements.txt
python course-demos/session-01-setup/check_env.py
python course-demos/session-01-setup/hello_bot.py
python -m pytest -q
```

## Hello Bot modes

```bash
python hello_bot.py            # 无Slack token时进入控制台模式
python hello_bot.py --mock     # Slack/console 都强制使用离线 echo 回复，不调用真实 LLM
python hello_bot.py --console --mock  # 即使已配置Slack token，也在本地控制台测试mock回复
```

有真实 Slack token 时（`SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`，App 需开启 Socket Mode），`hello_bot.py` 会连上 workspace 响应 @mention。被 @mention 后，同一 thread 里的后续消息不需要再次 @mention，bot 会继续回复。配置 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY` 时，回复由 LLM 生成；没有模型密钥或传入 `--mock` 时自动回到离线 echo 模式。

## LLM mock exercise

从 `course-demos` 目录运行 Python：

```python
from common.llm import call_llm
print(call_llm("You are a helpful assistant.", "Hello", mock="Hello from mock"))
```

未配置模型密钥时，上述调用返回固定结果。真实模型可按需安装 openai 或 anthropic 并在本地配置密钥；不要提交 `.env` 或密钥。测试会移除模型密钥，使用离线模式。

## 课堂练习

- [Session 1：诗词聊天机器人练习](practices/session-01-poem-bot.md)
