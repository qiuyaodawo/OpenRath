# Trading Agents

A **multi-role trading research** example: sequential **analyst** (with live market data), **bear** and **bull** researchers, **trader**, and **risk / PM**. It follows a “TradingAgents-style” narrative flow over a single user session, backed by the **local** sandbox and an OpenAI-compatible LLM.

## When to use this example

- You want to see **tool-augmented** `run_session_loop` (Alpha Vantage quote) followed by **pure reasoning** phases.
- You need a compact demonstration of **session handoff** across differently prompted agents sharing one chunk table.
- You are wiring **real external APIs** (market data) next to OpenRath session primitives.

## Prerequisites

- Python 3.10+ and [`uv`](https://github.com/astral-sh/uv).
- `OPENAI_API_KEY` set in the environment.
- `ALPHA_VANTAGE_API_KEY` set to a valid [Alpha Vantage](https://www.alphavantage.co/support/#api-key) API key (the example expects this variable; obtain your own key for production use).

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | LLM for all agents. |
| `OPENAI_BASE_URL` | No | OpenAI-compatible gateway URL. |
| `OPENAI_DEFAULT_MODEL` | No | Model id. |
| `ALPHA_VANTAGE_API_KEY` | Yes | Global quote endpoint used by the analyst tool. |

## How to run

From the repository `example/` directory:

```bash
export OPENAI_API_KEY=sk-...
export ALPHA_VANTAGE_API_KEY=your_alphavantage_key

uv run python trading_agents/main.py --ticker NVDA --as-of 2026-01-15
```

### Flags

| Flag | Meaning |
|------|---------|
| `--ticker` | US equity symbol (required), e.g. `AAPL`. |
| `--as-of` | Optional date label for reporting context only. |
| `--workdir` | Sandbox working directory (default `.workspace/` from CWD). |
| `--print-chunks` | Verbose one-line trace per new chunk. |

The user message tells the analyst to call the quote tool first; keep that convention if you change prompts.

## Data and limitations

- Quotes and metadata depend on **Alpha Vantage** availability, rate limits, and symbol coverage.
- This example is **research and education oriented**; it does not execute trades or provide financial advice.

## Related code

- `main.py` — CLI and session bootstrap.
- `workflow.py` — `TradingAgentsWorkflow` phase order.
- `agents.py` — per-role system prompts.
- `tools.py` — `AlphaVantageGlobalQuoteTool` implementation.
- `_env.py` — strict checks for API configuration at startup.

## License

Follows the same license as the parent OpenRath project.

## Documentation note

These examples are documented like reusable agent skills: explicit **when-to-use** triggers, environment tables, and runnable commands. For curated SKILL.md collections and IDE install paths, see [best-skills](https://github.com/xstongxue/best-skills) and the [Cursor Skills documentation](https://cursor.com/docs/context/skills).
