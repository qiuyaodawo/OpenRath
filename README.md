# OpenRath

![OpenRath logo](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/logo.png)

**OpenRath** is an open-source multi-agent framework. You can compose APIs in a PyTorch-like style: session lifecycle, workflow orchestration, tool dispatch, and sandbox backends evolve together on a session graph woven from agents and sessions.

## Recent updates

- 2026-05-12: Released `v1.0.0` and opened the codebase and docs to the community.

> For more info on OpenRath, head over to our docs [https://openrath.terox.cn/index.html](https://openrath.terox.cn/index.html).

---

## Core highlights

Many stacks keep conversation state, orchestration logic, and execution environments separate: each agent holds its own message list or inner while-loop, the outer layer uses graphs or hand-written steps, and sandboxes or shells are bolted on later. That works for demos, but whole histories get copied across agent boundaries, the execution environment drifts from the workspace the session points at, and at cluster scale it is hard to say which branch and context a round belongs to. OpenRath treats the session as the primary carrier through a run (analogous to a tensor advancing through computation, without replacing PyTorch itself). The split differs in five ways below.

### Sandbox as the execution backend of a session

Separate ledgers for messages and where commands actually run stay in sync only by hand. After machine or directory changes, or tighter isolation, tool landing points and the workspace implied by the conversation often diverge, which hurts reproducibility and audit. Here backend choice chain-loads off the same object, much like putting data on a device. After a dialogue-and-tool round, ownership of the active sandbox is written back into the returned session so later dispatch still targets the same workflow outcome.

![Sandbox as session backend](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/backend.png)

### Context through chunk tables for better reuse in multi-agent collaboration

Flat message lists encourage whole-history copies and repeated stitching of system prompts and tool results, so it is hard to grab semantic slices while context length and traffic grow. This project keeps an ordered chunk table for system, user, assistant, tool feedback, and related rows; agent-side instructions are prepended before user chunks in the loop for structured sharing and composition. Session fork and merge primitives are described in the Session chapter of the user guide.

### Session-first loops instead of agent-first loops for a sparse agent cluster

A common pattern is a small inner loop per agent (read, model, tools) wrapped by outer orchestration, which yields nested loops and unnecessary completions at a fixed cadence when many roles exist. The default path is session-centric: completions and tool rounds interleave on one evolving session; agents attach to the workflow mainly as prompts and sampling configuration, not each with its own closed executor, which fits sparse clusters better when only part of the roles should activate.

![Session-first loop](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/session.png)

### Dynamic multi-agent fleets: automatic session-graph tracking

When topology is wired by hand or an external DAG, lineage often depends on ad-hoc IDs and log excerpts. At scale it becomes hard to say which fork or merge produced a given output. With session-graph tracking enabled, new sessions carry lineage metadata and register centrally into a queryable session graph for dialogue and tool traces; this has nothing to do with autograd and only records execution and conversation.

### Modular workflows: compose and orchestrate cleanly

If one agent type owns prompts, network I/O, tools, and the loop, inheritance and callbacks stack up and even changing a system prompt or sampling field pulls the whole class. Workflows expose a forward step that takes a session and returns an updated session; agent-side settings sit in parameter-like objects; networking and sandbox dispatch live with the loop executor so module boundaries stay clearer for nesting and reuse.

![Workflow composition](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/workflow.png)

---

## Quickstart

### Install from PyPI

```bash
pip install openrath
```

Optional OpenSandbox dependencies:

```bash
pip install "openrath[opensandbox]"
```

### Install from source

```bash
git clone https://github.com/Rath-Team/OpenRath.git
cd OpenRath
pip install .
```

### Configure the OpenSandbox backend (optional)

```bash
pip install "openrath[opensandbox]"
# or: pip install ".[opensandbox]"
```

You need a running OpenSandbox server (typically Docker). At the repo root, use `scripts/launch_opensandbox.sh` or `launch_opensandbox.bat` to sync the optional dependency, generate `.sandbox.toml`, and start `opensandbox-server`; see the script comments for details.

Export `OPEN_SANDBOX_DOMAIN` (default if unset in check scripts: `127.0.0.1:8080`) and any API keys your deployment requires. Run `scripts/check_opensandbox.sh` or `check_opensandbox.bat` to verify imports and `GET /health`.

Set the backend to `opensandbox` in-session with a spec; see `example/sandbox_backend_opensandbox.py` and the user guide chapter on sandbox backends.

---

## Documentation

Build Sphinx locally:

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

The HTML output is under `docs/_build/html/`.

---

## Examples

Sample OpenRath entry points:

1. [`session_usage.py`](example/session_usage.py): fork and detach, session loop with a local workspace binding, plus session compression at the main entry.
2. [`sandbox_backend_local.py`](example/sandbox_backend_local.py): session loop on the local subprocess sandbox; compares unbound workspace vs binding the repository root as the workspace.
3. [`sandbox_backend_opensandbox.py`](example/sandbox_backend_opensandbox.py): same shape on the OpenSandbox backend; requires an OpenSandbox stack.
4. [`custom_tool_usage.py`](example/custom_tool_usage.py): FlowToolCall subclass and tool mode wiring on the model side.
5. [`trading_agents/`](example/trading_agents/): an OpenRath reimplementation of [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Tauric Research, multi-agent LLM finance stack). Roles stay in a workflow; sessions and tools follow this framework; CLI entry is `main.py`.
6. [`engineering_agents/`](example/engineering_agents/): an OpenRath reimplementation of one scenario from [ClawTeam](https://github.com/HKUDS/ClawTeam) (HKUDS, multi-agent software-engineering automation). Nested workflows (e.g. Lead, FeatureSquad, backend pairs, QA) live in the subfolder.
7. [`research_transformer/`](example/research_transformer/): a **Transformer-metaphor** academic pipeline (literature vs reproduction branches over N layers, optional figure tool, final polish) demonstrating story-first composition on `Session`/`Workflow`; default sandbox root is `example/research_transformer/.workspace/`.

<div align="center">
  <img src="https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/research_transformer.png" alt="Research Transformer" style="width: 360px; height: auto;" />
</div>

The folders above that reimplement or storyboard upstream scenarios (`trading_agents`, `engineering_agents`, and similar) are for demonstrating complex orchestration only; they are not guarantees about upstream behavior. Using upstream names still means following those repositories’ licenses and terms.

---

## How OpenRath maps onto PyTorch

| Layer | PyTorch | OpenRath | Brief parallel |
| ----- | ------- | -------- | -------------- |
| Flowing carrier | Tensor | Session | Advances along compute or dialogue; state can be read again and appended. |
| Execution structure | Compute graph | Session Graph | Graphs encode dependencies; sessions carry multi-agent dialogue and tool traces. |
| Execution backend | GPU / CPU | Sandbox | Where compute lands maps to the isolation environment where commands and tools actually run. |
| Invoke surface | Kernel / op | Tool | Smallest callable surface the backend actually executes. |
| State / hyperparameters | `nn.Parameter` | `flow.AgentParam` | Agents are not classic executors; the object is closer to typed configuration or parameters. |
| Modularity | `nn.Module` | `flow.Workflow` | Recursive composition of child modules. |

1. **Session / tensor**

In OpenRath a session carries ordered semantic chunks, not a numeric array. Like a tensor in PyTorch at the center of data flow and execution, fork and detach names follow PyTorch habits.

In OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
b = a.fork()  # like clone()
c = a.detach()
```

In PyTorch

```python
import torch

a = torch.ones(3, requires_grad=True)
b = a.clone()
c = a.detach()
```

2. **Session graph / compute graph**

In PyTorch a multiply attaches the new tensor to the graph and `grad_fn` points at the backward node; after `detach` on a leaf, `grad_fn` is None. In OpenRath the session tracks identity and fork metadata: each session has a stable id, fork products record parent session ids, and detach products no longer declare a parent chain.

In OpenRath

```python
from rath.session import Session

a = Session.from_user_message("Hello, how are you?")
b = a.fork()
c = a.detach()

print(a.id)
print(b.parent_session_ids)
print(c.parent_session_ids)
```

In PyTorch

```python
import torch

a = torch.tensor([1.0], requires_grad=True)
b = a * 2
c = a.detach()

print("a:", a)
print("b grad_fn:", b.grad_fn)
print("c.grad_fn:", c.grad_fn)
```

3. **Sandbox / device**

OpenRath models the sandbox backend in a device-like way: the session binds to an execution environment and working directory; chunk contents are not automatically rewritten when you rebind. The API mirrors PyTorch’s `to(device)` pattern: build the object, then declare where it runs.

In OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")  # spec: host workspace path
a = a.to("opensandbox", spec="./")
```

In PyTorch

```python
import torch

a = torch.ones(2, 3)
a = a.to("cuda:0")
```

4. **Kernel / tool**

In PyTorch, kernels or high-level ops take placed tensors, run numerically on that device, and return tensors. In OpenRath, the tool path takes structured payloads; the current sandbox interprets them inside an isolation boundary and returns command or file feedback into session chunks.

The call shapes line up: prepare inputs, invoke a thin API, and let the runtime do the heavy work.

In OpenRath

```python
from rath.flow.tool import flow_tool_files_list
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")

tool_result = flow_tool_files_list(a, path="./")
```

In PyTorch

```python
import torch
import torch.nn.functional as F

logits = torch.tensor(
    [
        [2.0, 1.0, 0.1, -1.0, 0.3],
        [0.2, 3.1, 0.5, 0.1, -0.4],
        [1.2, 0.7, 2.5, 0.3, 0.1],
    ]
)
target = torch.tensor([0, 1, 2])

loss = F.cross_entropy(logits, target)
```

5. **Agent state / parameters**

Module parameters in PyTorch register on the module dict and optimizers collect tensors by name. `AgentParam` in OpenRath binds two pieces into one: agent-side session chunks seeded from the agent prompt (a stable prefix before each completion) and a `Provider` with model name and sampling-style request fields.

In OpenRath

```python
from rath import flow
from rath.session import Session

agent = flow.AgentParam(
    agent_session=Session.from_agent_prompt("You are a helpful assistant."),
    provider=flow.Provider(model="glm-5.1"),
)
```

In PyTorch

```python
import torch
from torch import nn

weight = nn.Parameter(torch.randn(1024, 4096))
```

6. **Workflow / module**

Workflow code stays modular and composable, much like PyTorch `Module`. With sessions and chunks maintained by the framework, implementers mainly structure workflow composition and business logic.

In OpenRath

```python
from rath import flow
from rath.flow.tool import FlowToolCall
from rath.session import Session, run_session_loop


class Agent(flow.Workflow):
    def __init__(
        self,
        system_prompt: str,
        provider: flow.Provider,
        tools: list[FlowToolCall] | None = None,
    ) -> None:
        super().__init__()
        self.tools = list(tools or [])
        self.agent = flow.AgentParam(
            agent_session=Session.from_agent_prompt(system_prompt),
            provider=provider,
        )

    def forward(self, session: Session) -> Session:
        return run_session_loop(
            user_session=session,
            agent_session=self.agent.agent_session,
            agent_provider=self.agent.provider,
            tools=self.tools,
        )


agent_model = Agent(
    system_prompt="You are a helpful assistant.",
    provider=flow.Provider(model="glm-5.1"),
)

user_session = Session.from_user_message(
    "List all files in the current directory. Summarize what you found."
)
user_session = user_session.to("local", spec="./")
out_session = agent_model(user_session)
```

In PyTorch

```python
import torch
import torch.nn as nn


class Linear(nn.Module):
    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.randn(out_features, in_features))
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x @ self.weight.T + self.bias


model = Linear(4, 2)
x = torch.randn(3, 4)
y = model(x)
```

---

## License

OpenRath uses a BSD-style license; see [LICENSE](LICENSE) at the repository root.
