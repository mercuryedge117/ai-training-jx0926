# 第4课 · LLM 文本摘要

**演示要点**：直接消费 `slack-simulator` 的事故消息做真实摘要；重点讲长文本超出上下文窗口时的 **Map-Reduce 分段摘要**。

```bash
python summarize.py                          # 摘要 #incidents 频道（自动选择单次/map-reduce）
python summarize.py --channel "#product"     # 换频道
python summarize.py --chunk-size 6           # 调小分块，强制走map-reduce观察两阶段过程
```

**面试预埋**："长文本超出模型上下文时如何处理？"——Map（分段各自摘要）→ Reduce（汇总摘要的摘要），以及它与滑动窗口的取舍。
