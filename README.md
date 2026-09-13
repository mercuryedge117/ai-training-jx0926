# AI Training

企业级 AI 应用训练课程：从项目环境、Slack 数据、LLM 调用入口开始，逐步扩展到消息处理、摘要、任务提取、RAG、风险分析、编排集成与评分。

当前仓库已发布 Session 1 代码及必要共享模块。完整课程架构见 [course-demos/ARCHITECTURE.md](course-demos/ARCHITECTURE.md)。

## 通用准备

建议使用 Python 3.12。每个 session 的具体运行命令请进入对应目录查看说明。

如需配置本地密钥，复制 `course-demos/.env.example` 为 `course-demos/.env`，再填入自己的 Slack 或 LLM 密钥。不要提交 `.env`。

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

## Practices

- [Session 1：诗词聊天机器人](course-demos/session-01-setup/practices/session-01-poem-bot.md)
