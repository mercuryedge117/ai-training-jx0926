# 项目架构：完整课程模块依赖图

给助教/讲师核对项目全貌用的一张图，覆盖全部14个 session、6大模块。**学员不用在第1课就通读这份**——随着课程推进，对应模块会逐一在正文里出现；第1课只需要看 [ARCHITECTURE.md](ARCHITECTURE.md) 里那两个脚本。

```mermaid
flowchart LR
    subgraph SIM["slack-simulator（教学数据）"]
        personas["config/personas.yaml<br/>scenarios/*.yaml"]
        gen["generate_messages.py<br/>(需LLM key)"]
        msgs["data/sample_messages.jsonl"]
        gt["data/ground_truth.json"]
        kb["kb/*.md（RAG知识库）"]
        personas --> gen --> msgs
        gen --> gt
    end

    subgraph COMMON["common/（共享库，全部支持mock降级）"]
        llm["llm.py<br/>call_llm() / call_llm_tools()"]
        retr["retriever.py<br/>chunkers + TfidfIndex"]
        emb["embeddings.py<br/>EmbeddingIndex<br/>(真实OpenAI embedding 或 offline hash mock)"]
        nlp["nlp.py<br/>summarize() / extract_tasks()<br/>（精简版）"]
        asst["assistant.py<br/>scan_risks / summarize_channel<br/>extract_action_items / ask_kb<br/>（四项能力，三方共用）"]
        asst --> llm
        asst --> nlp
        asst --> retr
    end

    subgraph M1["模块1 消息处理 · 第1-3课"]
        s1["check_env.py / hello_bot.py"]
        s2["verify_signature.py / echo_server.py"]
        s3["pipeline.py / chat_agent.py"]
    end

    subgraph M2["模块2 摘要 · 第4-5课"]
        s4["summarize.py"]
        s5["judge.py / compare_prompts.py"]
    end

    subgraph M3["模块3 任务提取 · 第6-7课"]
        s6["extract_tasks.py"] -->|extracted_tasks.json| s7["task_system.py<br/>dedupe/sort/remind"]
    end

    subgraph M4["模块4 RAG + 风险预警 · 第8-9课"]
        s8["rag_index.py"]
        s9a["faq_bot.py"]
        s9b["risk_monitor.py"]
    end

    subgraph M5["模块5 编排与集成 · 第10-11课"]
        s10["orchestrator.py<br/>(router + 3个子Agent + 防死循环)"]
        s11["app.py<br/>(叙述层：5模块串联)"] -->|outputs/*.json| s12
    end

    s12["run_eval.py<br/>第12课：P/R/F1 打分 → 简历数字"]

    subgraph M6["模块6 工具调用与对外暴露 · 第13-14课"]
        s13a["tools.py<br/>schema + 实现"]
        s13b["guardrails.py<br/>allowlist / dry-run / 审计日志"]
        s13c["agent_tools.py<br/>function calling 循环<br/>MAX_TOOL_HOPS"]
        s13a --> s13c
        s13b --> s13c
        s14a["mcp_server.py<br/>JSON-RPC over stdio<br/>initialize / tools-list / tools-call"]
        s14b["api.py<br/>FastAPI + Pydantic<br/>healthz / readyz / ask / digest"]
        s14c["Dockerfile + DEPLOY.md"]
        s14b --> s14c
    end

    s13c --> llm
    s14a --> asst
    s14b --> asst
    s11 --> asst

    s3 --> llm
    s4 --> llm
    s5 --> llm
    s8 --> retr
    s8 --> emb
    s9a --> retr
    s9b --> llm
    s10 --> nlp

    msgs --> s4
    msgs --> s6
    msgs --> s9b
    msgs --> s10
    msgs --> asst
    gt --> s5
    gt --> s10
    gt --> s12
    kb --> s8
    kb --> s9a
    kb --> asst

    TESTS["tests/（131个用例，全部mock模式，见 requirements-dev.txt / CI）"]
    TESTS -.exercises.-> COMMON
    TESTS -.exercises.-> M1
    TESTS -.exercises.-> M2
    TESTS -.exercises.-> M3
    TESTS -.exercises.-> M4
    TESTS -.exercises.-> M5
    TESTS -.exercises.-> M6
```

## 怎么读这张图

- **左到右 = 数据生成 → 共享库 → 课程模块 → 打分**：`slack-simulator/` 产出的 JSONL + ground truth 是所有教学模块的统一输入；`common/` 是所有模块共享的基础设施；第12课把第11课的输出对照 ground truth 打分，闭环。
- **common/ 是唯一的"生产级细节"聚集地**：LLM 调用降级、chunking、TF-IDF/embedding 双检索、摘要/抽取逻辑都在这里——学生看这几个文件就能理解"离线可跑 + 有 key 自动升级"的设计原则，而不用在十几个 session 里重复看到同一段降级逻辑。
- **`assistant.py` 是"教学版 vs 可复用版"的分界线**：图上有三条箭头指向它——`app.py`（第11课，边跑边打印）、`mcp_server.py` 和 `api.py`（第14课，返回数据、保持安静）。**逻辑只有一份，形态有两种。** 第三个调用方出现的那一刻，就是复制粘贴不再可接受的那一刻。
- **模块3 是唯一有严格文件依赖的模块**（session-06 写 `extracted_tasks.json`，session-07 读它）——其余模块都是并列地消费 `slack-simulator/data/`，没有跨session的文件耦合，这也是为什么模块4、5可以并行讲或调换顺序。
- **模块6 的方向和前面五个相反**：模块 1–5 是"我们调模型"，第13课是"模型调我们的工具"，第14课是"别人的 agent 和别人的浏览器调我们"。**依赖箭头掉了个头，护栏就成了必需品**——`guardrails.py` 存在的全部理由。
- **测试套件（`tests/`）覆盖全部模块**，且全部在 mock 模式下运行（不需要任何 API key），是 CI（`.github/workflows/ci.yml`）里跑的内容——学生/助教改代码后跑 `pytest` 就知道有没有破坏其他模块的假设。
