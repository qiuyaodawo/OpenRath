# OpenRath

简体中文 · [English](README.md)

**OpenRath** 是面向开源社区的多智能体框架：开发者可以用接近 PyTorch 书写习惯的组合式接口，会话管理、Workflow 编排、工具分发与沙箱后端在一个由 Agent 和 Session 组成的 Session Graph 上演进。

---

## 最新更新

- 2026-05-12：我们发布了 `v1.0.0` 版本，代码与文档已向社区开源！

---

## 核心特点

### 以 Session 为中心的系统设计

### 基于数据块表的 Context 设计，大幅提高 Agent 协作时 Context 复用率

### 选择 Session-Loop 而不是 Agent-Loop，稀疏运行 Agent Cluster

### 自动 Session Graph 管理，迈向多智能体集群

### 模块化实现、编排与管理 Workflow 与 Agent

---

## 快速开始

### PyPI 安装

```bash
pip install openrath
```

可选装载 OpenSandbox 相关依赖时使用：

```bash
pip install "openrath[opensandbox]"
```

### 源码安装

```bash
git clone https://github.com/Rath-Team/OpenRath.git
cd OpenRath
pip install .
```

### 配置 OpenSandbox 后端（可选）

需要走 OpenSandbox 隔离执行时，在源码装上附加 extra：

```bash
pip install "openrath[opensandbox]"
# 或 pip install ".[opensandbox]"
```

---

## OpenRath 与 PyTorch 在各层设计理念上的对照

| 层 | PyTorch | OpenRath | 相似之处 |
| --- | --- | --- | --- |
| 流动单元 | Tensor | Session | 沿计算 / 对话轴向前推进、可反复读取与追加状态的核心载体。 |
| 执行结构 | 计算图 | Session Graph | 图记录算子依赖；Session 记录 Multi Agent 的对话与工具轨迹。 |
| 执行后端 | GPU / CPU | Sandbox | 把 “算在哪里” 换成 “工具与命令跑在哪个隔离环境”。 |
| 调用接口 | Kernel / op | Tool | 对外是可调用的最小执行单元，由后端实际跑起来。 |
| 状态与超参 | `nn.Parameter` | `flow.AgentParam` | Agent 不作为执行者，而是类似参数的数据维护者。 |
| 模块化 | `nn.Module` | `flow.Workflow` | 组合子模块，便于递归装配。 |

1. **流动单元**

在 OpenRath

```python
a = Session.from_user_message("Please impl a full-stack todo app with auth, DB, React frontend.")
b = a.fork() # like clone()
c = a.detach()
```

在 Pytorch

```python
a = Tensor.ones()
b = a.clone()
c = a.detach()
```

2. **执行结构**

在 OpenRath

```python
a = Session.from_user_message("Hello, how are you?")
b = a.fork()
c = a.detach()

print(a.id) # 78584f27-4a4b-4faa-bc36-de47ab698bbc
print(b.parent_session_ids) # UUID('78584f27-4a4b-4faa-bc36-de47ab698bbc')
print(c.parent_session_ids) # None
```

在 Pytorch

```python
a = torch.Tensor([1.0], requires_grad=True)
b = a * 2
c = a.detach()

print("a:", a) # tensor([1.], requires_grad=True)
print("b parent:", b.grad_fn.next_functions) # <MulBackward0 object at 0x...>
print("c.grad_fn:", c.grad_fn) # None
```

3. **执行后端**

在 OpenRath

```python
a = Session.from_user_message("Please impl a full-stack todo app with auth, DB, React frontend.")
a = a.to(sandbox="local", spec="./") # spec means host workspace dir path.
a = a.to(sandbox="opensandbox", spec="./")
```

在 Pytorch

```python
a = Tensor.ones()
a = a.to("cuda:0")
```

4. **调用接口**

在 OpenRath

```python
from rath.flow.tool import flow_tool_files_list

a = Session.from_user_message("Please impl a full-stack todo app with auth, DB, React frontend.")
a = a.to(sandbox="local", spec="./") # spec means host workspace dir path.

call = flow_tool_files_list(path="./")
a.require_sandbox().dispatch(call)
```

在 Pytorch

```python
from torch.nn.functional import cross_entropy

logits = torch.tensor([
    [2.0, 1.0, 0.1, -1.0, 0.3],
    [0.2, 3.1, 0.5, 0.1, -0.4],
    [1.2, 0.7, 2.5, 0.3, 0.1]
])
target = torch.tensor([0, 1, 2])

loss = cross_entropy(logits, target)
```

5. **状态与超参**

```python
from rath import flow
from rath.session import Session

agent = flow.AgentParam(
    agent_session=Session.from_agent_prompt("You are a helpful assistant."),
    provider=flow.Provider(model="glm-5.1"),
)
```

在 Pytorch

```python
import torch
from torch import nn

weight = nn.Parameter(
    torch.randn(1024, 4096)
)
```

6. **模块化**

```python
from rath import flow
from rath.session import Session, run_session_loop

class Agent(flow.Workflow):
    def __init__(
        self,
        system_prompt: str,
        model: str,
        tools: list[flow.tool.FlowToolCall] | None = None,
    ):
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

agent = flow.Agent(
    system_prompt="You are a helpful assistant.",
    model="glm-5.1",
)

user_session = Session.from_user_message("List all files in the current directory. And summarize the result.")
user_session = user_session.to("local", spec="./")
out_session = agent(user_session)
```

在 Pytorch

```python
import torch
import torch.nn as nn

class Linear(nn.Module):
    def __init__(
        self, 
        in_features: int, 
        out_features: int
    ):
        super().__init__()
        self.weight = nn.Parameter(
            torch.randn(out_features, in_features)
        )
        self.bias = nn.Parameter(
            torch.zeros(out_features)
        )

    def forward(self, x: torch.Tensor):
        return x @ self.weight.T + self.bias

model = Linear(4, 2)
x = torch.randn(3, 4)
y = layer(x)
```

---

## 案例

仓库内附带可运行的最小示例：

---

## 文档

优先阅读托管站点：https://docs.openrath.com

可在本地构建 Sphinx：

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

生成的静态页位于 `docs/_build/html/`。

---

## License

OpenRath 采用 BSD 风格许可证，全文见仓库根目录 [`LICENSE`](LICENSE)。
