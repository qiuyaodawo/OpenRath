# OpenRath

English · [简体中文](README_zh.md)

OpenRath is an open-source multi-agent framework for Python. You can assemble APIs in a Torch-like composition style—session handling, Workflow orchestration, tool dispatch, and sandbox backends—as they evolve together on a Session Graph built from agents and Sessions.

---

## Recent updates

- 2026-05-12: Released `v1.0.0`; code and docs are available to the community as open source.

---

## Highlights

### Session-centric Sandbox, Tool, and Workflow design

Session keeps an ordered tape of system / user / assistant / tool chunks—the primary state carried through a multi-agent run. Sandbox backends execute tool payloads for real; `ToolTable` maps OpenAI-shaped tool names to `FlowToolCall` values or in-process `@tool` callables; `Workflow` stitches multiple `AgentParam` modules via `forward(session) -> session`. All three revolve around the same Session tape instead of drifting apart.

### Managed Session graphs toward larger agent fleets

Chunk tables and lineage at the conversation layer preserve a trace across chat turns, tool round-trips, and nested sub-workflows. Grounding responsibilities in Sessions makes it simpler to attach larger clusters of agents, branch or merge transcripts, or plug in auditing—all on top of one abstraction (topology and orchestration policies stay under your product and deployment control).

### Modular Workflow and agent implementation

`Workflow` subclasses register `AgentParam` children through attributes, much like `nn.Module` composes submodules. Tool factories live under `rath.flow.tool`; sandbox execution lives under `rath.backend`, and the two stay deliberately decoupled. Split files by domain and team-owned sub-workflows, then wire them in a top-level `Workflow`.

### Conceptual parallels with PyTorch

The table helps intuition migration only—OpenRath does not provide autograd or tensor kernels.

| Layer | PyTorch | OpenRath | Similarity |
| ----- | ------- | -------- | ---------- |
| Flowing unit | Tensor | Session | The core carrier that progresses along the computation / dialogue axis and can be re-read as new state arrives. |
| Execution structure | Compute graph | Session chunks + lineage | Graphs record operator dependencies; Sessions capture dialogue plus tool traces and grow across rounds. |
| Execution backend | GPU / CPU | Sandbox | “Where arithmetic runs” becomes “which isolated runtime executes commands and tools.” |
| Call surface | Kernel / op | Tool | The smallest externally invokable execution unit handed to a backend. |
| State & knobs | `nn.Parameter` | `flow.AgentParam` | Pins per-role prompts on the assistant side plus model provider hints for reuse. |
| Modularity | `nn.Module` | `flow.Workflow` | Recursive composition, explicit `forward`, named enumeration helpers. |

---

## Quickstart

### PyPI installation

```bash
pip install openrath
```

Optional OpenSandbox extra:

```bash
pip install "openrath[opensandbox]"
```

### Source installation

```bash
git clone https://github.com/Rath-Team/OpenRath.git
cd OpenRath
pip install .
```

### Environment variables

Copy `.env.example` to `.env` and fill at least:

| Variable | Purpose |
| -------- | ------- |
| `OPENAI_API_KEY` | Compatible OpenAI-style API credential |
| `OPENAI_BASE_URL` | Gateway base URL for Chat Completions |
| `OPENAI_DEFAULT_MODEL` | Fallback model ID when callers omit `model` |

OpenSandbox knobs and mirrored server secrets are annotated inside `.env.example`.

### Configure the OpenSandbox backend (optional)

When sessions should execute inside OpenSandbox, add the optional extra atop your source checkout:

```bash
pip install "openrath[opensandbox]"
# or: pip install ".[opensandbox]"
```

You still need a healthy OpenSandbox deployment plus allowlisting / bind policies—the hosted docs explain the setup alongside `.env.example`.

---

## Examples

Minimal runnable demos live under `example/`:

Engineering-focused multi-agent (local sandbox directory):

```bash
cd example/engineering_agents
python main.py --goal "Full-stack todo app with auth, DB, React frontend."
# optional: --workdir /path/to/sandbox/root (defaults to .workspace/)
```

Trading-oriented multi-agents (`ALPHA_VANTAGE_API_KEY` required):

```bash
cd example/trading_agents
python main.py --ticker NVDA --as-of 2026-01-15
# same optional --workdir flag
```

Request an Alpha Vantage key at https://www.alphavantage.co/support/#api-key

---

## Documentation

Prefer the hosted handbook: https://docs.openrath.com

Build Sphinx locally whenever needed:

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

HTML output appears under `docs/_build/html/`.

---

## License

OpenRath ships under a BSD-style license; see [`LICENSE`](LICENSE) in the repository root.
