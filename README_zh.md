# OpenRath

![OpenRath logo](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/logo.png)

<p align="center">
  <a href="https://pypi.org/project/openrath/"><img src="https://img.shields.io/pypi/v/openrath.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/openrath/"><img src="https://img.shields.io/pypi/pyversions/openrath.svg" alt="Python"></a>
  <a href="https://github.com/Rath-Team/OpenRath/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-BSD--3--Clause-blue.svg" alt="License"></a>
  <a href="https://linux.do"><img src="https://img.shields.io/badge/LINUX-DO-FFB003.svg?logo=data:image/svg%2bxml;base64,DQo8c3ZnIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgd2lkdGg9IjEwMCIgaGVpZ2h0PSIxMDAiPjxwYXRoIGQ9Ik00Ni44Mi0uMDU1aDYuMjVxMjMuOTY5IDIuMDYyIDM4IDIxLjQyNmM1LjI1OCA3LjY3NiA4LjIxNSAxNi4xNTYgOC44NzUgMjUuNDV2Ni4yNXEtMi4wNjQgMjMuOTY4LTIxLjQzIDM4LTExLjUxMiA3Ljg4NS0yNS40NDUgOC44NzRoLTYuMjVxLTIzLjk3LTIuMDY0LTM4LjAwNC0yMS40M1EuOTcxIDY3LjA1Ni0uMDU0IDUzLjE4di02LjQ3M0MxLjM2MiAzMC43ODEgOC41MDMgMTguMTQ4IDIxLjM3IDguODE3IDI5LjA0NyAzLjU2MiAzNy41MjcuNjA0IDQ2LjgyLS4wNTYiIHN0eWxlPSJzdHJva2U6bm9uZTtmaWxsLXJ1bGU6ZXZlbm9kZDtmaWxsOiNlY2VjZWM7ZmlsbC1vcGFjaXR5OjEiLz48cGF0aCBkPSJNNDcuMjY2IDIuOTU3cTIyLjUzLS42NSAzNy43NzcgMTUuNzM4YTQ5LjcgNDkuNyAwIDAgMSA2Ljg2NyAxMC4xNTdxLTQxLjk2NC4yMjItODMuOTMgMCA5Ljc1LTE4LjYxNiAzMC4wMjQtMjQuMzg3YTYxIDYxIDAgMCAxIDkuMjYyLTEuNTA4IiBzdHlsZT0ic3Ryb2tlOm5vbmU7ZmlsbC1ydWxlOmV2ZW5vZGQ7ZmlsbDojMTkxOTE5O2ZpbGwtb3BhY2l0eToxIi8+PHBhdGggZD0iTTcuOTggNzAuOTI2YzI3Ljk3Ny0uMDM1IDU1Ljk1NCAwIDgzLjkzLjExM1E4My40MjYgODcuNDczIDY2LjEzIDk0LjA4NnEtMTguODEgNi41NDQtMzYuODMyLTEuODk4LTE0LjIwMy03LjA5LTIxLjMxNy0yMS4yNjIiIHN0eWxlPSJzdHJva2U6bm9uZTtmaWxsLXJ1bGU6ZXZlbm9kZDtmaWxsOiNmOWFmMDA7ZmlsbC1vcGFjaXR5OjEiLz48L3N2Zz4=" alt="LINUX DO"></a>
</p>

---

<div align="center">

[English](README.md) · 简体中文

</div>

---

**OpenRath** 是一个开源的多智能体框架。你可以使用类似 PyTorch 的编程风格来组合 API：会话生命周期、工作流编排、工具分发以及沙箱后端，在由智能体和会话编织的会话图上协同演进。

## 近期动态

- 2026-05-12：发布 `v1.0.0`，面向社区开放代码和文档。

> 如需了解更多关于 OpenRath 的信息，请访问我们的文档 [https://openrath.terox.cn/index.html](https://openrath.terox.cn/index.html)。

---

## 核心亮点

许多技术栈将会话状态、编排逻辑和执行环境割裂开来：每个智能体维护自己的消息列表或内部循环，外层使用图或手写步骤协调，沙箱或 Shell 则在后期接入。这种方式用于演示尚可，但在跨智能体边界时会完整拷贝整段历史，执行环境与会话指向的工作区逐渐漂移，在集群规模下也难以判断某轮交互属于哪个分支和上下文。OpenRath 将 **会话（Session）** 作为贯穿一次运行的核心载体（类似于张量在计算中传递，但并不替代 PyTorch 本身）。具体差异体现在以下五个方面。

### 沙箱作为会话的执行后端

消息记录与命令实际执行的位置通常各自独立维护，仅靠手动同步。在机器或目录变更、或隔离要求更严格的情况下，工具的落地位置与会话隐含的工作区容易偏离，损害可复现性和审计能力。在 OpenRath 中，沙箱后端的选择从同一个对象链式加载，类似于将数据放到指定设备上。经过一轮对话和工具调用后，活动沙箱的所有权会写回返回的 Session 中，后续的调度仍指向相同的工作流结果。

![沙箱作为会话后端](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/backend.png)

### 通过分块表管理上下文，提升多智能体协作中的复用能力

扁平的消息列表鼓励全量历史拷贝和系统提示、工具结果的反复拼接，在上下文长度和流量增长时很难高效地抽取语义片段。本项目维护一个有序的分块表，涵盖系统、用户、助手、工具反馈等类型的行；智能体侧的指令在循环中作为用户分块的前置部分，实现结构化的共享和组合。Session 的 fork 和 merge 操作详见用户指南中的 Session 章节。

### 以会话为中心的循环（Session-first），而非以智能体为中心的循环（Agent-first），适配稀疏智能体集群

常见模式是每个智能体维护一个小型内部循环（读取、模型调用、工具执行），由外部编排层包裹。当存在多个角色时，这会产生嵌套循环，且以固定频率触发不必要的补全。OpenRath 的默认路径以会话为中心：补全和工具轮次交替作用于一个不断演进的会话上；智能体主要作为提示词和采样配置接入工作流，而非各自封闭的执行器。在只需要部分角色激活的稀疏集群中，这种方式更为合适。

![会话中心循环](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/session.png)

### 动态多智能体集群：自动追踪会话图

当拓扑结构由手写代码或外部 DAG 串联时，谱系追踪往往依赖临时 ID 和日志片段。规模扩大后很难说清是哪个 fork 或 merge 产生了某个输出。开启会话图追踪后，新建的 Session 会携带谱系元数据，并集中注册到一个可查询的会话图中，用于追踪对话和工具轨迹；这与自动求导（autograd）无关，仅记录执行和对话过程。

### 模块化工作流：清晰的组合与编排

如果一个智能体类型同时管理提示词、网络 I/O、工具和循环，继承关系和回调会不断堆叠，哪怕只是修改系统提示词或采样字段也会牵连整个类。OpenRath 的工作流暴露一个 `forward` 方法，接收一个 Session 并返回更新后的 Session；智能体侧的设置存放在类似参数的对象中；网络通信和沙箱调度归入循环执行器，使模块边界更加清晰，便于嵌套和复用。

![工作流组合](https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/workflow.png)

---

## 快速开始

### 从 PyPI 安装

```bash
pip install openrath
```

可选的 OpenSandbox 依赖：

```bash
pip install "openrath[opensandbox]"
```

### 从源码安装

```bash
git clone https://github.com/Rath-Team/OpenRath.git
cd OpenRath
pip install .
```

### 配置 OpenSandbox 后端（可选）

```bash
pip install "openrath[opensandbox]"
# 或者：pip install ".[opensandbox]"
```

你需要运行一个 OpenSandbox 服务器（通常使用 Docker）。在仓库根目录下，使用 `scripts/launch_opensandbox.sh` 或 `launch_opensandbox.bat` 来同步可选依赖、生成 `.sandbox.toml` 并启动 `opensandbox-server`；详见脚本注释。

设置环境变量 `OPEN_SANDBOX_DOMAIN`（检查脚本中的默认值：`127.0.0.1:8080`）以及部署所需的 API 密钥。运行 `scripts/check_opensandbox.sh` 或 `check_opensandbox.bat` 来验证导入和 `GET /health` 接口。

在 Session 中通过 spec 将后端设置为 `opensandbox`；参考 `example/sandbox_backend_opensandbox.py` 以及用户指南中关于沙箱后端的章节。

---

## 文档

本地构建 Sphinx 文档：

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

HTML 输出位于 `docs/_build/html/` 目录下。

---

## 示例

以下是 OpenRath 的示例入口点：

1. [`session_usage.py`](example/session_usage.py)：fork 和 detach 用法、绑定本地工作区的会话循环，以及主入口处的会话压缩。
2. [`sandbox_backend_local.py`](example/sandbox_backend_local.py)：基于本地子进程沙箱的会话循环；对比无绑定工作区与将仓库根目录绑定为工作区的区别。
3. [`sandbox_backend_opensandbox.py`](example/sandbox_backend_opensandbox.py)：在 OpenSandbox 后端上的相同形态；需要部署 OpenSandbox 服务。
4. [`custom_tool_usage.py`](example/custom_tool_usage.py)：FlowToolCall 子类定义和模型侧工具模式的接入方式。
5. [`trading_agents/`](example/trading_agents/)：对 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（Tauric Research 的多智能体 LLM 金融栈）的 OpenRath 重实现。角色保留在工作流中；会话和工具由本框架接管；CLI 入口为 `main.py`。
6. [`engineering_agents/`](example/engineering_agents/)：对 [ClawTeam](https://github.com/HKUDS/ClawTeam)（HKUDS 的多智能体软件工程自动化）某一场景的 OpenRath 重实现。嵌套的工作流（如 Lead、FeatureSquad、后端对、QA）位于子目录中。
7. [`research_transformer/`](example/research_transformer/)：一个 **Transformer 隐喻** 的学术流水线（文献 vs 复现分支经过 N 层、可选的绘图工具、最终润色），展示了基于 `Session`/`Workflow` 的故事优先组合方式；默认沙箱根目录为 `example/research_transformer/.workspace/`。

<div align="center">
  <img src="https://raw.githubusercontent.com/Rath-Team/OpenRath/main/docs/source/_static/research_transformer.png" alt="Research Transformer" style="width: 360px; height: auto;" />
</div>

以上重实现或剧本化上游场景的目录（`trading_agents`、`engineering_agents` 及类似目录）仅用于演示复杂编排能力；它们不代表上游项目的行为或效果。使用上游项目名称仍须遵守其仓库的许可证和条款。

---

## OpenRath 与 PyTorch 的映射关系

| 层次 | PyTorch | OpenRath | 简要对照 |
| ----- | ------- | -------- | -------------- |
| 流动载体 | Tensor | Session | 沿计算或对话推进；状态可被再次读取和追加。 |
| 执行结构 | 计算图 | Session Graph | 图表达依赖关系；Session 承载多智能体对话和工具轨迹。 |
| 执行后端 | GPU / CPU | Sandbox | 计算落地的位置对应命令和工具实际执行的隔离环境。 |
| 调用面 | Kernel / op | Tool | 后端实际执行的最小调用单元。 |
| 状态 / 超参 | `nn.Parameter` | `flow.AgentParam` | 智能体并非经典执行器；该对象更接近类型化的配置或参数。 |
| 模块化 | `nn.Module` | `flow.Workflow` | 子模块的递归组合。 |

### 1. Session / Tensor

在 OpenRath 中，一个 Session 携带的是有序的语义分块，而非数值数组。与 PyTorch 中 Tensor 处于数据流和执行的核心位置一样，fork 和 detach 的命名也沿用了 PyTorch 的习惯。

在 OpenRath 中：

```python
from rath.session import Session

a = Session.from_user_message(
    "请实现一个带认证、数据库和 React 前端的完整待办应用。"
)
b = a.fork()  # 类似 clone()
c = a.detach()
```

在 PyTorch 中：

```python
import torch

a = torch.ones(3, requires_grad=True)
b = a.clone()
c = a.detach()
```

### 2. Session Graph / Compute Graph

在 PyTorch 中，一个乘法操作会将新 Tensor 附加到计算图上，`grad_fn` 指向前向节点；在叶节点执行 `detach` 后 `grad_fn` 为 None。在 OpenRath 中，Session 追踪身份和 fork 元数据：每个 Session 拥有稳定的 id，fork 产物记录父 Session id，detach 产物不再声明父链。

在 OpenRath 中：

```python
from rath.session import Session

a = Session.from_user_message("Hello, how are you?")
b = a.fork()
c = a.detach()

print(a.id)
print(b.parent_session_ids)
print(c.parent_session_ids)
```

在 PyTorch 中：

```python
import torch

a = torch.tensor([1.0], requires_grad=True)
b = a * 2
c = a.detach()

print("a:", a)
print("b grad_fn:", b.grad_fn)
print("c.grad_fn:", c.grad_fn)
```

### 3. Sandbox / Device

OpenRath 以类似 device 的方式建模沙箱后端：Session 绑定到执行环境和工作目录；重新绑定时分块内容不会被自动重写。API 镜像了 PyTorch 的 `to(device)` 模式：先构建对象，再声明其运行位置。

在 OpenRath 中：

```python
from rath.session import Session

a = Session.from_user_message(
    "请实现一个带认证、数据库和 React 前端的完整待办应用。"
)
a = a.to("local", spec="./")  # spec: 宿主机工作区路径
a = a.to("opensandbox", spec="./")
```

在 PyTorch 中：

```python
import torch

a = torch.ones(2, 3)
a = a.to("cuda:0")
```

### 4. Kernel / Tool

在 PyTorch 中，内核或高级操作接收已放置的 Tensor，在该设备上执行数值运算，并返回 Tensor。在 OpenRath 中，工具路径接收结构化载荷；当前沙箱在隔离边界内解释它们，并将命令或文件反馈返回到 Session 分块中。

调用形态一致：准备输入、调用薄 API、让运行时完成繁重工作。

在 OpenRath 中：

```python
from rath.flow.tool import flow_tool_files_list
from rath.session import Session

a = Session.from_user_message(
    "请实现一个带认证、数据库和 React 前端的完整待办应用。"
)
a = a.to("local", spec="./")

tool_result = flow_tool_files_list(a, path="./")
```

在 PyTorch 中：

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

### 5. Agent 状态 / 参数

PyTorch 中的 Module 参数注册在模块字典上，优化器按名称收集 Tensor。OpenRath 中的 `AgentParam` 将两部分绑定在一起：从智能体提示词填充的 Session 分块（每次补全前的稳定前缀），以及携带模型名称和采样请求字段的 `Provider`。

在 OpenRath 中：

```python
from rath import flow
from rath.session import Session

agent = flow.AgentParam(
    agent_session=Session.from_agent_prompt("You are a helpful assistant."),
    provider=flow.Provider(model="glm-5.1"),
)
```

在 PyTorch 中：

```python
import torch
from torch import nn

weight = nn.Parameter(torch.randn(1024, 4096))
```

### 6. Workflow / Module

工作流代码保持模块化和可组合性，类似于 PyTorch 的 `Module`。由于 Session 和分块由框架维护，实现者主要关注工作流的组合结构和业务逻辑。

在 OpenRath 中：

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
    "列出当前目录下的所有文件，并总结你的发现。"
)
user_session = user_session.to("local", spec="./")
out_session = agent_model(user_session)
```

在 PyTorch 中：

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

OpenRath 使用 BSD 风格的许可证；详见仓库根目录的 [LICENSE](LICENSE)。
