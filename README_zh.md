# OpenRath

简体中文 · [English](README.md)

**OpenRath** 是面向开源社区的多智能体框架：开发者可以用接近 PyTorch 书写习惯的组合式接口，会话管理、Workflow 编排、工具分发与沙箱后端在一个由 Agent 和 Session 组成的 Session Graph 上演进。

---

## 最新更新

- 2026-05-12：我们发布了 `v1.0.0` 版本，代码与文档已向社区开源！

---

## 核心特点

### 以 Session 为中心的 Sandbox、Tool、Workflow 设计

Session 保存有序的 system / user / assistant / tool 分块，是贯穿一次多智能体运行的主状态。沙箱后端负责真正执行工具载荷；`ToolTable` 把 OpenAI 风格的工具名映射到 `FlowToolCall` 或进程内 `@tool`；`Workflow` 把多个 `AgentParam` 按 `forward(session) -> session` 组合起来。三者都围绕同一条 Session 磁带协同，而不是各起炉灶。

### 自动 Session Graph 管理，迈向多智能体集群

框架在会话层维护分块与谱系信息，使得多轮补全、工具往返、子工作流嵌套时仍有一条可追踪的时间线。把「谁说了什么、工具回了什么」固化在 Session 上，后续接更大的 agent 集群、分支 / 合并会话或外挂审计，都更容易在统一抽象上扩展（具体拓扑与调度仍由你的业务与部署决定）。

### 模块化实现、编排与管理 Workflow 与 Agent

`Workflow` 子类用属性注册 `AgentParam`，类似 `nn.Module` 挂子模块；工具工厂放在 `rath.flow.tool`，沙箱执行放在 `rath.backend`，二者刻意解耦。你可以按域拆文件、按团队拆子工作流，再在顶层 `Workflow` 里装配。

### OpenRath 与 PyTorch 在各层设计理念上的对照

下表只用于直觉迁移，OpenRath 不提供微分与张量算子。

| 层 | PyTorch | OpenRath | 相似之处（简述） |
| --- | --- | --- | --- |
| 流动单元 | Tensor | Session | 都是沿计算 / 对话轴向前推进、可反复读取与追加状态的核心载体。 |
| 执行结构 | 计算图 | Session 分块与谱系 | 图记录算子依赖；Session 记录对话与工具轨迹，支持多轮展开。 |
| 执行后端 | GPU / CPU | Sandbox | 把「算在哪里」换成「工具与命令跑在哪个隔离环境」。 |
| 调用接口 | Kernel / op | Tool | 对外是可调用的最小执行单元，由后端实际跑起来。 |
| 状态与超参 | `nn.Parameter` | `flow.AgentParam` | 把「这一角色的 system 侧提示 + 使用的模型提供方」绑在模块上复用。 |
| 模块化 | `nn.Module` | `flow.Workflow` | 组合子模块、实现 `forward`、支持命名枚举，便于递归装配。 |

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

### 配置环境变量

复制 `.env.example` 为 `.env`，至少填写：

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_KEY` | 兼容 OpenAI 协议的密钥 |
| `OPENAI_BASE_URL` | Chat Completions 网关基址 |
| `OPENAI_DEFAULT_MODEL` | 未显式传 `model` 时的默认模型 ID |

其余 OpenSandbox、服务端密钥镜像等字段见 `.env.example` 内注释。

### 配置 OpenSandbox 后端（可选）

需要走 OpenSandbox 隔离执行时，在源码装上附加 extra：

```bash
pip install "openrath[opensandbox]"
# 或 pip install ".[opensandbox]"
```

仍会依赖你自行部署可用的 OpenSandbox 服务与 allowlist／卷挂载策略；详见文档中 OpenSandbox 相关章节与 `.env.example`。

---

## 案例

仓库内附带可运行的最小示例：

工程化多智能体（本地沙箱目录）：

```bash
cd example/engineering_agents
python main.py --goal "Full-stack todo app with auth, DB, React frontend."
# 可选: --workdir 自定义沙箱根路径（默认 .workspace/）
```

交易研究向多智能体（需 `ALPHA_VANTAGE_API_KEY`）：

```bash
cd example/trading_agents
python main.py --ticker NVDA --as-of 2026-01-15
# 同上可配 --workdir
```

密钥申请见：https://www.alphavantage.co/support/#api-key

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
