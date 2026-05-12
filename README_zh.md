# OpenRath

简体中文 · [English](README.md)

**OpenRath** 是一套面向开源社区的多智能体框架。你可以用接近 PyTorch 的组合方式组织 API：在由 Agent 与 Session 编织成的 **Session Graph** 上，统一演进会话生命周期、Workflow 编排、工具分发与沙箱后端。

---

## 最新更新

- 2026-05-12：发布 `v1.0.0`，代码与文档向社区开放。

---

## 核心特点

许多框架把对话状态、编排逻辑与执行环境分开维护：各智能体自持消息列表或内层 while 循环，外层再用有向图或手写步骤调度，沙箱与 Shell 往往事后拼接。Demo 可行，但跨智能体边界易重复拷贝整段历史，执行环境与会话所指向的工作区也容易漂移；集群规模上来后，难以统一回答当前轮次处于哪条分支的何种上下文。OpenRath 将会话视作贯穿一次运行的主载体（可与“张量沿计算推进”类比，但不替代 PyTorch），在下面五条上采用不同切分。

### 将 Sandbox 抽象为 Session 的执行后端

常见栈把消息与命令实际跑在何处分成两本账，靠应用层同步。换机、换目录或加严隔离时，工具落点与对话所指工作区不一致的情况并不少见，复现与审计都更困难。此处将会话与后端选择绑在同一链式调用上，语义接近把数据放到指定设备；对话与工具往返结束后，活跃沙箱的归属写回输出会话，后续分发仍对准同一工作流结果。

### 基于数据块表的 Context 设计，大幅提高 Agent 协作时 Context 复用率

扁平消息列表在多角色传递时常整段复制或反复拼接系统提示与工具结果，难以按语义块取用，上下文长度与传输量随之膨胀。本框架用有序分块表表达角色、用户、助手与工具反馈等行；智能体侧指令在循环中固定置于用户分块之前，便于结构化共享与组合。会话 fork、merge 等原语见用户指南中的会话章节。

### 选择 Session-Loop 而不是 Agent-Loop，稀疏运行 Agent Cluster

普遍模式是每个智能体内置读入、模型、工具的小循环，外层再包装编排，角色一多易产生嵌套循环与固定节拍下的无效补全。默认路径以会话为中心：在同一演化会话上交替完成补全与工具轮次；智能体以提示与采样配置等形式挂在工作流上，而非各占一套封闭执行器，更适合只有部分角色需要激活的稀疏集群。

### 动态多智能体集群：基于全自动的 Session Graph 管理

手写编排或外部 DAG 维护拓扑时，会话血缘多依赖自建标识与日志摘录。规模扩大后，难以系统回答某条输出从哪次 fork 或合并而来。在开启会话图跟踪时，新会话携带谱系元数据并集中登记，形成可查询的会话图，便于追踪对话与工具轨迹；与自动微分无关，仅保留执行与对话记录。

### 模块化实现、编排与管理你的 Workflow

若单一智能体类型同时包揽提示、网络访问、工具与循环，继承与回调易堆叠，只改系统提示或采样参数也会牵动整类。工作流对外提供前向：接收会话、返回更新后的会话；智能体侧设定集中在参数式对象中；网络与沙箱分发放在循环执行器一侧，模块边界更利于嵌套与复用。

---

## 快速开始

### PyPI 安装

```bash
pip install openrath
```

若需使用 OpenSandbox 相关依赖，可安装可选扩展：

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

```bash
pip install "openrath[opensandbox]"
# 或：pip install ".[opensandbox]"
```

安装后需能跑 OpenSandbox 服务端（通常依赖 Docker）。在项目根可直接用 `scripts/launch_opensandbox.sh` 或 `launch_opensandbox.bat`：同步可选依赖、生成 `.sandbox.toml` 并拉起 `opensandbox-server`，具体步骤见脚本内说明。

在运行环境中导出 `OPEN_SANDBOX_DOMAIN`（自检脚本未设置时的默认值为 `127.0.0.1:8080`）以及部署所需的 API 密钥。自检可运行 `scripts/check_opensandbox.sh` 或 `check_opensandbox.bat`（导入 SDK 与访问 `/health`）。

会话内将后端设为 `opensandbox` 并传入 spec；示例见 `example/sandbox_backend_opensandbox.py`，原理见用户指南中的沙箱后端一章。

---

## 文档

优先阅读在线文档：[https://docs.openrath.com](https://docs.openrath.com)

在本地构建 Sphinx：

```bash
git clone https://github.com/Rath-Team/OpenRath.git
uv sync --group dev --group docs
uv run sphinx-build -M html docs/source docs/_build
```

生成的 HTML 位于 `docs/_build/html/`。

---

## 案例

以下为一些使用 OpenRath 的 Example：

1. `[session_usage.py](example/session_usage.py)`：演示会话的 fork、detach 以及绑定本地工作区后的会话循环，主入口处附带对会话压缩接口的调用。
2. `[sandbox_backend_local.py](example/sandbox_backend_local.py)`：在本地子进程沙箱上跑通会话循环，对比无工作目录绑定与将仓库根目录绑定为工作区两种 spec。
3. `[sandbox_backend_opensandbox.py](example/sandbox_backend_opensandbox.py)`：在 OpenSandbox 沙箱上跑通会话循环；需拉起 OpenSandbox 运行栈。
4. `[custom_tool_usage.py](example/custom_tool_usage.py)`：展示 FlowToolCall 子类与模型侧工具模式的衔接方式。
5. `[trading_agents/](example/trading_agents/)`：对 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（Tauric Research，多智能体 LLM 金融交易框架）的 OpenRath 重写。多角色仍以 Workflow 串联，会话与工具分发遵循本框架，命令行入口见 main.py。
6. `[engineering_agents/](example/engineering_agents/)`：对 [ClawTeam](https://github.com/HKUDS/ClawTeam)（HKUDS，多智能体软件工程自动化）中某一示例场景的 OpenRath 重写。嵌套 Workflow（如 Lead → FeatureSquad、后端成对与 QA）在子目录内完成。

上述两个子目录仅用于演示复杂编排，不构成对上游项目功能、输出或行为的担保；使用上游名称时尚须遵守对应仓库的许可与条款。

---

## OpenRath 与 PyTorch 在各层设计理念上的对照


| 层     | PyTorch        | OpenRath          | 相似之处                              |
| ----- | -------------- | ----------------- | --------------------------------- |
| 流动单元  | Tensor         | Session           | 沿计算 / 对话轴向前推进；可反复读取并追加稳定状态。       |
| 执行结构  | 计算图            | Session Graph     | 图刻画依赖；Session 承载多智能体对话与工具轨迹。      |
| 执行后端  | GPU / CPU      | Sandbox           | 算力所落之处，对应命令与工具实际运行的隔离环境。            |
| 调用接口  | Kernel / op    | Tool              | 对外暴露的最小可调用单元，由后端实际执行。             |
| 状态与超参 | `nn.Parameter` | `flow.AgentParam` | Agent 不承担典型执行器角色，更像带类型的配置或参数载体。       |
| 模块化   | `nn.Module`    | `flow.Workflow`   | 递归组合子模块，装配复杂系统。                   |


1. **会话/张量**

会话在 OpenRath 中是承载若干语义分块与时间顺序的载体，不是数值数组。类似 Tensor 在 PyTorch 中是数据流动和执行的核心，并且会话的 fork 与 detach 的命名贴近 PyTorch 习惯。

在 OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
b = a.fork()  # like clone()
c = a.detach()
```

在 PyTorch

```python
import torch

a = torch.ones(3, requires_grad=True)
b = a.clone()
c = a.detach()
```

2. **会话图/计算图**

PyTorch 里一次乘法会把新张量挂到计算图上，grad_fn 指向产生该张量的反向节点；对叶子再做 detach 后 grad_fn 为空。而在 OpenRath 里，会话维护身份与分叉元数据：每个会话有稳定的 id，fork 产物记录父会话 id 列表，detach 产物则不再声明父链。

在 OpenRath

```python
from rath.session import Session

a = Session.from_user_message("Hello, how are you?")
b = a.fork()
c = a.detach()

print(a.id)
print(b.parent_session_ids)
print(c.parent_session_ids)
```

在 PyTorch

```python
import torch

a = torch.tensor([1.0], requires_grad=True)
b = a * 2
c = a.detach()

print("a:", a)
print("b grad_fn:", b.grad_fn)
print("c.grad_fn:", c.grad_fn)
```

3. **沙箱/设备**

OpenRath 将沙箱后端抽象成 `Device` 一样的类型，沙箱与会话一对一绑定，设置 Session 的执行环境与会话所认的工作目录，分块内容不因此而自动改写。并且 OpenRath 采用类似 PyTorch 的 `to(device)` 调用：先构造对象，再声明在哪里执行。

在 OpenRath

```python
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")  # spec：主机工作区路径
a = a.to("opensandbox", spec="./")
```

在 PyTorch

```python
import torch

a = torch.ones(2, 3)
a = a.to("cuda:0")
```

4. **核函数/工具**

在 PyTorch 中核函数或高层算子接收已放置张量，在张量所在设备上完成数值工作，返回值仍是张量。在 OpenRath 中，工具调用路径则接收结构化载荷，由当前沙箱解释并在隔离边界内产生命令结果或文件内容等反馈，再写回会话分块。

OpenRath 与 PyTorch 的调用接口在表面形状上对齐：准备输入、调用一层很薄的 API，再交给运行时处理重活。

在 OpenRath

```python
from rath.flow.tool import flow_tool_files_list
from rath.session import Session

a = Session.from_user_message(
    "Please impl a full-stack todo app with auth, DB, React frontend."
)
a = a.to("local", spec="./")

tool_result = flow_tool_files_list(a, path="./")
```

在 PyTorch

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

5. **智能体状态/参数**

模块参数在 PyTorch 中注册到模块字典，优化器按名字收集并更新张量数据。在 OpenRath 中 AgentParam 将两段信息绑成一体：一段由 from_agent_prompt 播种的智能体会话分块，决定模型在每轮补全前稳定看到的前缀；另一段 Provider 携带模型名与采样等请求级字段。

在 OpenRath

```python
from rath import flow
from rath.session import Session

agent = flow.AgentParam(
    agent_session=Session.from_agent_prompt("You are a helpful assistant."),
    provider=flow.Provider(model="glm-5.1"),
)
```

在 PyTorch

```python
import torch
from torch import nn

weight = nn.Parameter(torch.randn(1024, 4096))
```

6. **工作流/模块**

OpenRath 将 Workflow 的实现变成一件可模块化、组件化的事情，类似 PyTorch 的 `Module`。在 Session 与分块由框架维护的前提下，实现者主要组织 Workflow 的模块化组合与业务逻辑。

在 OpenRath

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

在 PyTorch

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

OpenRath 采用 BSD 风格许可证，全文见仓库根目录 [`LICENSE`](LICENSE)。
