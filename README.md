# OpenRath

English · [简体中文](README_zh.md)

OpenRath is an open-source multi-agent framework. You compose APIs close to familiar PyTorch style: session lifecycle, Workflow wiring, tools, and sandbox backends evolve together on a Session Graph woven from Agents and Sessions.

---

## Recent updates

- 2026-05-12: Tagged `v1.0.0` and opened the codebase and docs to the community.

---

## Highlights

### Session-centric system design

### Context via chunk tables, improving reuse when Agents collaborate

### Session-Loop over Agent-Loop for sparse Agent Cluster execution

### Automatic Session Graph management toward multi-agent fleets

### Modular implementation, orchestration, and management of Workflows and Agents

---

## Quickstart

### Install from PyPI

```bash
pip install openrath
```

Optional OpenSandbox extras:

```bash
pip install "openrath[opensandbox]"
```

### Install from source

```bash
git clone https://github.com/Rath-Team/OpenRath.git
cd OpenRath
pip install .
```

### OpenSandbox backend (optional)

Attach the optional extra on top of your checkout when sessions should execute in OpenSandbox:

```bash
pip install "openrath[opensandbox]"
# or: pip install ".[opensandbox]"
```

---

## How OpenRath maps onto PyTorch (by layer)

Analogies guide intuition only—OpenRath does not ship autograd or tensor kernels.

| Layer | PyTorch | OpenRath | Parallel (short) |
| ----- | ------- | -------- | ---------------- |
| Flowing carrier | Tensor | Session | Advances along compute / dialogue; append and reread stable state. |
| Execution structure | Compute graph | Session Graph | Graphs encode op deps; Sessions record multi-agent chat + tool traces. |
| Runtime | GPU / CPU | Sandbox | “Where math runs” → “which isolation shell runs commands/tools.” |
| Invoke surface | Kernel / op | Tool | Minimal callable surfaced to backends. |
| State / knobs | `nn.Parameter` | `flow.AgentParam` | Agents are not executors—they hold configuration akin to typed parameters. |
| Modularity | `nn.Module` | `flow.Workflow` | Compose children recursively. |

### 1. Flowing carrier

OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
b = a.fork()  # like clone()
c = a.detach()
```

PyTorch

```python
import torch

a = torch.ones(3, requires_grad=True)
b = a.clone()
c = a.detach()
```

### 2. Execution structure

OpenRath

```python
from rath.session import Session

a = Session.from_user_message("Hello, how are you?")
b = a.fork()
c = a.detach()

print(a.id)
print(b.parent_session_ids)
print(c.parent_session_ids)
```

PyTorch

```python
import torch

a = torch.tensor([1.0], requires_grad=True)
b = a * 2
c = a.detach()

print("a:", a)
print("b grad_fn:", b.grad_fn)
print("c.grad_fn:", c.grad_fn)
```

### 3. Runtime / “device”

OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")  # working directory on the host
a = a.to("opensandbox", spec="./")
```

PyTorch

```python
import torch

a = torch.ones(2, 3)
a = a.to("cuda:0")
```

### 4. Invoke surface

OpenRath

```python
from rath.flow.tool import flow_tool_files_list
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")

payload = flow_tool_files_list(path="./")
a.require_sandbox().dispatch(payload)
```

PyTorch

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

### 5. State / hyper-parameters

OpenRath

```python
from rath import flow
from rath.session import Session

agent = flow.AgentParam(
    agent_session=Session.from_agent_prompt("You are a helpful assistant."),
    provider=flow.Provider(model="glm-5.1"),
)
```

PyTorch

```python
import torch
from torch import nn

weight = nn.Parameter(torch.randn(1024, 4096))
```

### 6. Modularity

OpenRath

```python
from rath import flow
from rath.flow.tool import FlowToolCall
from rath.session import Session, run_session_loop


class Agent(flow.Workflow):
    def __init__(
        self,
        system_prompt: str,
        model: str,
        tools: list[FlowToolCall] | None = None,
    ) -> None:
        super().__init__()
        self.tools = list(tools or [])
        self.agent = flow.AgentParam(
            agent_session=Session.from_agent_prompt(system_prompt),
            provider=flow.Provider(model=model),
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
    model="glm-5.1",
)

user_session = Session.from_user_message(
    "List all files in the current directory. Summarize what you found."
)
user_session = user_session.to("local", spec="./")
out_session = agent_model(user_session)
```

PyTorch

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

## Examples

The repository carries minimal runnable samples under `example/`.

---

## Documentation

Prefer the hosted site: https://docs.openrath.com

Build Sphinx offline:

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

HTML lands in `docs/_build/html/`.

---

## License

OpenRath is BSD-licensed—see [`LICENSE`](LICENSE).
