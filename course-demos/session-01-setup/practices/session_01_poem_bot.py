#!/usr/bin/env python3
"""Session 1 practice: answer a user's message with a classical poem line."""
import sys
from argparse import ArgumentParser
from pathlib import Path

COURSE_DEMOS = Path(__file__).resolve().parents[2]
if str(COURSE_DEMOS) not in sys.path:
    sys.path.insert(0, str(COURSE_DEMOS))

from common.llm import call_llm_safe

SYSTEM_PROMPT = """你是一个中文诗词聊天机器人。
理解用户的情绪或场景，然后用一句合适的古诗词回答。
输出格式：
诗句：<一句古诗词>
说明：<不超过30个字，说明为什么适合>
不要编造现代句子冒充古诗词。"""

ARCHITECTURE_MERMAID = """flowchart LR
    user["用户"] --> bot["session_01_poem_bot.py<br/>诗词聊天机器人"]
    bot --> shared["Session 1 共享能力<br/>course-demos/common/llm.py + course-demos/.env"]
    shared --> reply["古诗词回答"]
"""


def mock_poem_reply(text: str) -> str:
    if any(word in text for word in ("想家", "故乡", "家乡", "思念")):
        return "诗句：举头望明月，低头思故乡。\n说明：适合表达思乡之情。"
    if any(word in text for word in ("朋友", "分别", "离别", "送别")):
        return "诗句：海内存知己，天涯若比邻。\n说明：适合回应友情与距离。"
    if any(word in text for word in ("努力", "坚持", "学习", "考试")):
        return "诗句：长风破浪会有时，直挂云帆济沧海。\n说明：适合鼓励继续前行。"
    if any(word in text for word in ("难过", "累", "压力", "失落")):
        return "诗句：山重水复疑无路，柳暗花明又一村。\n说明：适合安慰低落时刻。"
    return "诗句：欲穷千里目，更上一层楼。\n说明：适合鼓励拓展视野。"


def answer_with_poem(text: str, mock: bool = False) -> str:
    text = text.strip()
    if mock:
        return mock_poem_reply(text)
    return call_llm_safe(
        system=SYSTEM_PROMPT,
        user=text,
        mock=lambda _system, _user: mock_poem_reply(text),
        temperature=0.2,
    )


def run_console(mock: bool = False) -> None:
    print("Poem bot. 输入 quit 退出。\n")
    while True:
        try:
            text = input("you> ")
        except EOFError:
            break
        if text.strip().lower() in ("quit", "exit", ""):
            break
        print("bot>", answer_with_poem(text, mock=mock))


def parse_args():
    parser = ArgumentParser(description="Session 1 practice: poem chat bot.")
    parser.add_argument("--mock", action="store_true",
                        help="force deterministic offline poem replies")
    parser.add_argument("--once", metavar="TEXT",
                        help="answer one message and exit")
    parser.add_argument("--diagram", action="store_true",
                        help="print this program's Mermaid architecture diagram")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.diagram:
        print(ARCHITECTURE_MERMAID)
        return
    if args.once is not None:
        print(answer_with_poem(args.once, mock=args.mock))
        return
    run_console(mock=args.mock)


if __name__ == "__main__":
    main()
