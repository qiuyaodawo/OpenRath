# Research Transformer

English · [简体中文](#说明)

This example tells a **story**: an academic “group meeting” pipeline framed like a **Transformer**—inputs become session chunks, two conceptual **heads** run literature synthesis versus reproduction scrutiny over **N layers**, an optional **side path** can sketch background figures, and a final **output head** applies “academic register” then **de-AI** polishing.

It uses the same OpenRath primitives as other examples: `Session`, `Workflow`, `run_session_loop`, and OpenAI-compatible `Provider` endpoints per role (configure models via env, not separate SDKs).

## Default workspace

Runtime artifacts go under **`example/research_transformer/.workspace/`** by default (`main.py` resolves it next to this package). Override with `--workdir`.

## Run (uv)

```bash
cd OpenRath
uv sync
set OPENAI_API_KEY=...   # Windows
uv run python example/research_transformer/main.py ^
  --research-question "Your research question" ^
  --supervisor-notes "Advisor constraints" ^
  --thesis-path path/to/senior_thesis_excerpt.txt ^
  --ddl-note "Defense in two weeks" ^
  --layers 2 ^
  --print-chunks
```

## Environment

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` | Required for real runs (unless `RESEARCH_TRANSFORMER_API_KEY` is set). |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible base. |
| `OPENAI_DEFAULT_MODEL` | Fallback model when a role-specific model is unset. |
| `RESEARCH_TRANSFORMER_API_KEY` / `RESEARCH_TRANSFORMER_BASE_URL` | Optional bundle override. |
| `RESEARCH_TRANSFORMER_MODEL_PACKAGER`, `..._LITERATURE`, `..._REWRITE`, `..._QA`, `..._VERIFIER`, `..._JARGON`, `..._DEAI`, `..._COMPRESSOR` | Per-station model names. |

**Compression:** Between the literature branch and the reproduction branch, and again before the final polish, the pipeline runs :class:`~rath.flow.compressor.Compressor` (``run_session_compress``) so the chunk table stays bounded. Use a cheap or fast model via ``RESEARCH_TRANSFORMER_MODEL_COMPRESSOR`` if you like. Pass ``--no-compress`` to keep the full transcript (debug only—context may explode).

Background images (optional): set `ZHIPU_API_KEY` or reuse `OPENAI_API_KEY` for the BigModel images endpoint used by `tools.py`, unless you pass `--skip-images`.

---

## 说明

本示例把**组会汇报式**学术流水线比喻成 Transformer：会话 chunk 表承载“嵌入”，文献整理与复现质疑两条分支像**多头**在 **N 层**上交替加深，可选配图工具像旁路，最后的**学术化 + 去 AI 味**像输出投影。大阶段之间使用 **`Compressor` / `run_session_compress`** 压缩会话，减轻上下文膨胀；需要完整留档时可加 **`--no-compress`**。

默认把沙箱工作目录绑定到 **`example/research_transformer/.workspace/`**，可用 `--workdir` 覆盖。
