# Session 1 练习：诗词聊天机器人

## 背景

创建一个聊天机器人。对于用户的每一句输入，程序先调用 LLM 理解用户含义，再输出一句合适的古诗词作为回答。

## 练习一：用 Mermaid 设计架构

目标：先用架构图设计程序，不急着写代码。

要求：

- 使用 [mermaid.live](https://mermaid.live/) 绘制 Mermaid 格式的架构图。
- 机器人接收用户输入，并返回一句合适的古诗词。
- 必须复用 Session 1 已有的 LLM 接口和配置，不能另外创建一套。
- 图中只画系统组件及其依赖关系，不展开 Prompt、模型选择、函数调用或错误处理。

可以从下面的 Mermaid 图开始，再根据自己的理解调整：

```mermaid
flowchart LR
    user["用户"] --> bot["诗词聊天机器人"]
    bot --> shared["Session 1 共享能力<br/>common/llm.py + .env"]
    shared --> reply["古诗词回答"]
```

设计提示：

- `course-demos/common/llm.py` 和 `course-demos/.env` 都属于图中的“Session 1 共享 LLM 能力”。
- 重点说明组件边界和依赖方向，实现细节留到练习二。

## 练习二：由架构图生成程序

目标：把练习一的 Mermaid 图交给 Codex 或 Claude，让 AI 根据架构约束生成程序。

将下面的任务和练习一的 Mermaid 图一起发给 AI：

```text
请根据 Mermaid 架构图生成一个 Python 诗词聊天机器人。

要求：
1. 程序文件名为 session_01_poem_bot.py。
2. 用户输入一句话，程序返回一句合适的古诗词和简短说明。
3. 复用 course-demos/common/llm.py，不要创建新的 LLM 客户端。
4. 使用 course-demos/.env 中的模型配置。
5. 支持 --mock、--once 和 --diagram。
6. --diagram 输出程序实际架构的 Mermaid 图。
```

生成后，检查程序是否遵守练习一的三个高层约束：输入经过诗词机器人、机器人复用
Session 1 共享能力、最终输出古诗词回答。

仓库中的 `session_01_poem_bot.py` 是参考实现。请先按照
[Session 1 Quick start](../README.md#quick-start)
创建 `.venv` 并安装依赖。在仓库根目录 `~/student` 激活虚拟环境，然后进入练习目录运行。

macOS (Terminal)：

```bash
source .venv/bin/activate
cd course-demos/session-01-setup/practices

python session_01_poem_bot.py --mock --once "我今天很想家"
python session_01_poem_bot.py --diagram
python session_01_poem_bot.py --mock
```

Windows (PowerShell)：

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location course-demos/session-01-setup/practices

python session_01_poem_bot.py --mock --once "我今天很想家"
python session_01_poem_bot.py --diagram
python session_01_poem_bot.py --mock
```

运行方式：

- `--mock`：强制使用离线固定规则，不调用真实 LLM。
- `--once "..."`：只回答一句输入，适合快速测试。
- `--diagram`：输出这个程序实际实现的 Mermaid 架构图，用来和练习一的设计图对比。

最后，把 `--diagram` 的输出粘贴到 [mermaid.live](https://mermaid.live/)，与练习一的图比较：

- 组件是否一一对应？
- 程序是否复用了 `common/llm.py + .env`？
- 实现有没有偏离原始架构？
