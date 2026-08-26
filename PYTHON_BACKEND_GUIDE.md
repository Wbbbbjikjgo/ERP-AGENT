Python 后端代码完全解析 — 从零理解智能采购助手

> 本文档按照逻辑阅读顺序，逐文件解析整个 Python 后端代码。每个章节包含文件路径、核心代码（含中文注释）、模块间关系和设计决策说明。按照顺序阅读，即可从零理解项目是如何运作的。

---

## 第1章 — 项目概览与架构

### 1.1 项目定位

本项目是一个基于 **Harness Engineering 架构**的 **ERP 智能采购助手**，专门服务于摩托车零部件采购管理业务。核心思想是：通过 AI Agent（基于 `deepagents` 框架）与已部署的 Java ERP 后端交互，实现供应商分析、采购订单管理（含人工审批）、图表生成、库存预警等智能化功能。

### 1.2 技术栈速览

| 技术 | 用途 | 版本/说明 |
|------|------|-----------|
| **deepagents** | Agent 框架 | 基于 LangGraph 的高层封装 |
| **LangGraph** | 状态图引擎 | Agent 执行引擎，支持中断/恢复 |
| **LangChain** | LLM 工具链 | ChatOpenAI（通义千问兼容接口） |
| **FastAPI** | Web 框架 | SSE 流式响应 |
| **FastMCP** | MCP 协议 | Agent ↔ ERP 的工具桥接 |
| **Docker SDK** | 沙箱 | 隔离代码执行环境 |
| **MongoDB (Motor)** | 数据库 | 会话/消息持久化 |
| **通义千问** | LLM | qwen-plus 模型 |

### 1.3 完整目录树（Python 后端）

```
src/
├── api_view/                          # Web 层 — FastAPI 对外服务
│   ├── web_main.py                    # FastAPI 应用入口
│   ├── web_config.py                  # MongoDB 连接配置
│   ├── agent_loader.py                # Agent 单例管理器（MongoDB持久化）
│   ├── mongodb_store.py               # LangGraph Store 的 MongoDB 实现
│   └── api/
│       ├── chat.py                    # SSE 流式对话（核心 347 行）
│       └── history.py                 # 历史会话 CRUD
│
├── agent/                             # Agent 层 — DeepAgent 核心
│   ├── main_agent.py                  # 主入口：create_main_agent() 7步组装
│   ├── config.py                      # 全局配置
│   ├── schema.py                      # Pydantic 数据模型（含 Harness 结构化状态）
│   ├── harness.py                     # ★Harness 编排（阶段状态机 + rubric 注入）
│   ├── harness_config.yaml            # ★Harness DSL 配置（四阶段/评审标准）
│   ├── env_utils.py                   # 环境变量加载
│   ├── log_utils.py                   # 日志工具
│   ├── middleware_config.py           # 子Agent中间件工厂（完整中间件栈）
│   ├── mcp_tools_bean.py              # MCP工具分类
│   ├── memory/
│   │   ├── prompts.py                 # 系统提示词
│   │   └── AGENTS.md                  # 全局操作手册
│   ├── subagents/
│   │   ├── loader.py                  # YAML加载+工具解析+输出契约校验
│   │   └── configs/
│   │       ├── procurement_analyst.yaml  # 分析专家配置
│   │       └── procurement_order.yaml    # 订单专家配置
│   ├── middlewares/                   # 7个自定义中间件
│   │   ├── sandbox_health.py          # 1. 沙箱健康检查
│   │   ├── context_injection.py       # 2. 上下文注入（工厂模式隔离）
│   │   ├── skills_sync.py             # 3. 技能同步（文件夹级增量+沙箱传输）
│   │   ├── user_skills_restore.py     # 4. 技能恢复（增量+空值保护）
│   │   ├── tools_summarization.py     # 5. 摘要监控
│   │   ├── memory_update.py           # 6. 偏好提取
│   │   └── sandbox_breaker.py         # 7. 熔断器
│   ├── tools/                         # 工具层（9个自定义工具+23个MCP=32）
│   │   ├── mcp_client.py              # MCP工具加载（重试/缓存/优雅降级）
│   │   ├── chart_generator.py         # 26种图表生成（沙箱内执行）
│   │   ├── web_search.py              # 网络搜索（通义千问搜索增强）
│   │   ├── web_fetch.py               # URL抓取+Skill安装（沙箱隔离流程）
│   │   ├── hitl_tools.py              # HITL人工介入
│   │   ├── assign_skill.py            # 技能分配
│   │   ├── download_sandbox_file.py   # 沙箱文件下载（真实Docker传输）
│   │   └── document_generator.py      # 文档生成（沙箱内输出）
│   └── backends/                      # 沙箱后端（7层安全防护）
│       ├── custom_opensandbox.py      # Docker SDK封装（30+方法）
│       ├── sandbox_setup.py           # 安全沙箱创建+多语言运行时
│       ├── sandbox_manager.py         # 五态生命周期管理
│       ├── sandbox_proxy.py           # 代理层（18个委托方法）
│       ├── sandbox_holder.py          # ★全局沙箱持有器（工具访问沙箱的桥梁）
│       └── seccomp.json               # seccomp 系统调用白名单
│
├── mcp_server/                        # MCP 网关 — Agent ↔ Java ERP
│   ├── server_main.py                 # FastMCP入口
│   ├── server_config.py               # 配置
│   ├── http_base.py                   # HTTP客户端
│   └── tools/
│       ├── suppliers_tools.py         # 供应商工具(5个)
│       ├── parts_tools.py             # 零部件工具(5个)
│       ├── order_tools.py             # 订单工具(7个)
│       └── inventory_tools.py         # 库存工具(6个)
│
├── skills/                            # 技能文件（文件夹级，9个skill）
│   ├── main/skill-management/         # 技能管理
│   ├── procurement/                   # 采购技能集（8个子skill）
│   └── pdf-image-text-extractor.md    # PDF提取技能
```

### 1.4 四层架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js :3000)                   │
│                 SSE 流式对话 + 中断交互                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/SSE
┌───────────────────────────▼─────────────────────────────────┐
│             api_view (FastAPI :8000)                         │
│  web_main.py → chat.py (SSE流) / history.py (会话管理)       │
│  agent_loader.py (Agent单例) / web_config.py (MongoDB)       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│             agent (DeepAgent 核心)                            │
│  main_agent.py → create_deep_agent()                         │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐ │
│  │ LLM      │ │ Backend   │ │ 7中间件    │ │ 子Agent(YAML)│ │
│  │ qwen-plus│ │ Docker沙箱 │ │ 健康/注入/ │ │ analyst/order│ │
│  │          │ │ Composite │ │ 同步/恢复/ │ │ 上下文协议    │ │
│  │          │ │ Backend   │ │ 摘要/偏好/ │ │ interrupt_on │ │
│  │          │ │           │ │ 熔断      │ │              │ │
│  └──────────┘ └───────────┘ └───────────┘ └──────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Tools: MCP(23个ERP工具) + Custom(9个) = 32个工具        ││
│  │ chart(26种) + web_search + web_fetch + install_skill    ││
│  │ + hitl_tools + download_sandbox_file + document_gen     ││
│  └─────────────────────────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────┘
                            │ SSE (MCP协议)
┌───────────────────────────▼─────────────────────────────────┐
│             mcp_server (FastMCP :9000)                       │
│  http_base.py (httpx AsyncClient 连接池)                     │
│  tools/: suppliers(5) + parts(5) + orders(7) + inventory(6) │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP REST
┌───────────────────────────▼─────────────────────────────────┐
│             Java ERP 后端 (:8081)                             │
│             http://47.92.108.163:8081                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.5 一次完整对话的数据流

当用户在前端输入"帮我分析所有供应商的供货能力"时：

1. **前端** → POST `/api/chat/stream` (SSE)
2. **chat.py** → `agent_loader.initialize()` 确保 Agent 已创建
3. **chat.py** → `agent.astream(input, stream_mode=["messages","values","custom"])` 开始流式执行
4. **main_agent.py** → 中间件栈依次执行 `before_agent()`（含 `HarnessPhaseMiddleware` 注入 rubric）
5. **LLM** 调用 `write_todos` → `TodoListMiddleware` 写入 `state.todos` → chat.py 从 values 流读取 → 发射 `todo_update` + `phase=planning`
6. **LLM** 决定委派给 `procurement-analyst` 子Agent
7. **子Agent** 调用 MCP 工具 → `mcp_client.py` → SSE 连接 MCP Server → `suppliers_tools.py` → HTTP 请求 Java ERP
8. **子Agent** 调用 `generate_chart` → 沙箱内 matplotlib 生成 PNG
9. **RubricMiddleware** grader 子Agent 对照 rubric 打分 → 发射 `review_result`，needs_revision 时打回重做
10. **chat.py** → 流结束 → 保存 display_messages + harness_trace 到 MongoDB → 发射 `done` 事件

---

## 第2章 — 基础设施层

> 这一层是整个项目的基础，提供环境变量加载、日志配置、数据模型定义和全局配置。所有其他模块都依赖这一层。

### 2.1 `src/agent/env_utils.py` — 环境变量加载（33行）

**作用**：从项目根目录的 `.env` 文件加载环境变量到 `os.environ`。整个项目的所有配置（API Key、数据库地址等）都通过此模块加载。

```python
"""
环境变量加载工具
从项目根目录 .env 文件加载环境变量到 os.environ
"""
import os
from pathlib import Path
from dotenv import load_dotenv  # python-dotenv 库，解析 .env 文件


def load_env():
    """加载项目根目录的 .env 文件"""
    # 项目根目录：src/agent/../../.env
    # __file__ 是本文件路径，parent.parent.parent 向上三级到项目根目录
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        # override=True 表示覆盖已存在的环境变量
        load_dotenv(env_file, override=True)
    else:
        print(f"⚠️ .env file not found at {env_file}")


def get_env(key: str, default: str = None) -> str:
    """获取环境变量（字符串类型）"""
    return os.getenv(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数类型的环境变量"""
    return int(os.getenv(key, str(default)))


# ⚡ 关键设计：模块加载时自动调用 load_env()
# 这意味着任何模块 import env_utils 时，.env 就已经加载完毕
load_env()
```

**被谁依赖**：`config.py`、`web_config.py`、`server_config.py`、`web_search.py` 等几乎所有需要配置的模块。

**.env 文件内容**：
```bash
DASHSCOPE_API_KEY=sk-f99ccd929fe146629c62c7339d3a9e55
MONGODB_URI=mongodb://localhost:27017
ERP_BASE_URL=http://47.92.108.163:8081
MCP_SERVER_URL=http://localhost:9000
SANDBOX_IMAGE=opensandbox/code-interpreter:v1.0.2
```

---

### 2.2 `src/agent/log_utils.py` — JSON 结构化日志（42行）

**作用**：为整个项目提供统一的 JSON 格式日志，按模块分配不同的 logger。

```python
"""
日志工具模块
结构化日志配置，按模块分 logger
"""
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器
    
    输出格式示例：
    {'timestamp': '2026-07-27T10:30:00', 'level': 'INFO', 
     'module': 'agent', 'message': 'Agent created'}
    """

    def format(self, record):
        # 构造 JSON 格式的日志条目
        log_entry = {
            "timestamp": datetime.now().isoformat(),  # ISO 8601 时间戳
            "level": record.levelname,                 # INFO/WARNING/ERROR
            "module": record.name,                     # logger 名称
            "message": record.getMessage(),            # 日志消息
        }
        # 如果有异常信息，附加 exception 字段
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return str(log_entry)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger
    
    Args:
        name: logger 名称，会显示在日志的 module 字段中
    
    设计要点：
    - 如果 logger 已有 handler 则不重复添加（避免日志重复输出）
    - 输出到 stdout（而非 stderr），方便容器日志收集
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# 预定义 5 个模块 logger，各模块按需导入使用
agent_logger = get_logger("agent")        # Agent 核心逻辑
mcp_logger = get_logger("mcp")            # MCP 工具相关
sandbox_logger = get_logger("sandbox")    # 沙箱操作
web_logger = get_logger("web")            # Web API 层
middleware_logger = get_logger("middleware")  # 中间件
```

**被谁依赖**：几乎所有模块都使用这些 logger 替代 `print()`。

---

### 2.3 `src/agent/schema.py` — Pydantic 数据模型（含 Harness 结构化状态）

**作用**：定义整个项目中流转的数据结构。这是类型安全的保障——所有请求、响应、上下文都通过这些模型约束。**本次改造新增了 Harness 四阶段的结构化状态模型**（Phase/PlanStep/Plan/ReviewResult），替代原先靠 prompt 软约束 + 正则猜测的脆弱实现。

```python
"""
数据模型定义
ProcurementContext、UserPreferences、ChatRequest 等 Pydantic 模型
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class UserPreferences(BaseModel):
    """用户偏好模型
    
    存储用户的个性化设置，由 MemoryUpdateMiddleware 自动提取并持久化。
    例如用户说"以后都用饼图"，preferred_chart_type 就会变成 "pie"。
    """
    preferred_output: str = Field(default="markdown", description="首选输出格式: markdown/table/json")
    preferred_chart_type: str = Field(default="bar", description="首选图表类型: bar/line/pie/scatter等")
    preferred_currency: str = Field(default="CNY", description="首选货币单位")
    preferred_language: str = Field(default="zh", description="首选语言: zh/en")
    recent_suppliers: List[str] = Field(default_factory=list, description="最近查询的供应商")
    recent_queries: List[str] = Field(default_factory=list, description="最近的查询记录")


class ProcurementContext(BaseModel):
    """采购上下文 — 每次请求注入到 Agent state
    
    这是 Harness 架构中"上下文注入"的核心数据结构。
    每次用户请求时，都会构造一个 ProcurementContext，
    通过 ContextInjectionMiddleware 注入到 Agent 的执行上下文中。
    """
    user_id: str = Field(default="default_user", description="用户ID")
    username: str = Field(default="用户", description="用户名")
    preferences: dict = Field(default_factory=dict, description="用户偏好字典")
    session_start: str = Field(default_factory=lambda: datetime.now().isoformat())


class ChatRequest(BaseModel):
    """聊天请求模型 — 前端 POST /api/chat/stream 的请求体"""
    message: str = Field(..., description="用户消息内容")
    thread_id: str = Field(default=None, description="会话线程ID，为空则创建新会话")
    user_id: str = Field(default="default_user", description="用户ID")
    username: str = Field(default="用户", description="用户名")


class ResumeRequest(BaseModel):
    """中断恢复请求模型 — 前端 POST /api/chat/{thread_id}/resume 的请求体"""
    resume: dict = Field(..., description="恢复数据，格式取决于中断类型")


class SSEEvent(BaseModel):
    """SSE 事件模型"""
    event: str = Field(..., description="事件类型: token/tool_start/tool_args/tool_result/tool_end/interrupt/done")
    data: dict = Field(default_factory=dict, description="事件数据")


class ConversationRecord(BaseModel):
    """会话记录 — 存储在 MongoDB conversations 集合中"""
    thread_id: str
    user_id: str
    title: str = "新对话"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class DisplayMessage(BaseModel):
    """前端展示消息 — 存储在 MongoDB display_messages 集合中
    
    这是经过处理后直接用于前端渲染的消息格式，
    与 LangGraph 内部的 Message 格式不同。
    """
    role: str = Field(..., description="角色: user/assistant/tool")
    content: str = Field(default="", description="消息内容")
    tool_calls: Optional[List[dict]] = Field(default=None, description="工具调用信息")
    source: Optional[str] = Field(default=None, description="来源: main/analyst/order")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# Harness 架构结构化状态模型（Planning → Executing → Review → Result）
# 用于替代 prompt 软约束：阶段、计划、评审结果都是可校验的强类型数据
# ============================================================

class Phase(str, Enum):
    """Harness 工作流阶段（图状态机，非文本猜测）"""
    thinking = "thinking"      # 思考中（初始态）
    planning = "planning"      # Planning：生成任务规划
    executing = "executing"    # Executing：调用工具/子Agent执行
    reviewing = "reviewing"    # Review：评审器校验结果
    result = "result"          # Result：结构化输出最终结果


class PlanStep(BaseModel):
    """规划中的单个步骤（对应 TodoListMiddleware 的 todo 项，但增加 result 回填）"""
    id: str = Field(..., description="步骤唯一标识")
    content: str = Field(..., description="步骤描述")
    status: Literal["pending", "in_progress", "completed"] = Field(
        default="pending", description="步骤状态"
    )
    result: Optional[str] = Field(default=None, description="步骤执行结果摘要")


class Plan(BaseModel):
    """Harness Planning 阶段的产物：结构化任务规划"""
    steps: List[PlanStep] = Field(default_factory=list, description="规划步骤列表")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    current_step: Optional[str] = Field(default=None, description="当前执行中的步骤 id")


class ReviewResult(BaseModel):
    """Harness Review 阶段的产物：评审器对执行结果的判定

    由 RubricMiddleware 的 grader 子Agent 产出，结构化而非 LLM 自述文本。
    """
    verdict: Literal[
        "satisfied", "needs_revision", "failed",
        "max_iterations_reached", "grader_error",
    ] = Field(..., description="评审判定")
    explanation: str = Field(default="", description="评审结论说明")
    criteria: List[dict] = Field(default_factory=list, description="逐条评审标准判定")
    iteration: int = Field(default=0, description="评审迭代次数")
```

**被谁依赖**：
- 基础模型：`chat.py`（ChatRequest/ResumeRequest）、`main_agent.py`（ProcurementContext）、`agent_loader.py`（ConversationRecord/DisplayMessage）、`context_injection.py`（ProcurementContext）。
- Harness 模型：`harness.py`（Phase/ReviewResult）、`chat.py`（阶段/评审结构化事件）。

---

### 2.4 `src/agent/config.py` — 全局配置（56行）

**作用**：集中管理所有配置参数。这是整个项目的"配置中心"——LLM、MongoDB、MCP、沙箱、Agent 限制等所有配置都在这里定义。

```python
"""
全局配置模块
LLM、Store、Checkpointer、沙箱连接参数
"""
import os
from langchain_openai import ChatOpenAI
from .env_utils import get_env, get_env_int  # 依赖 env_utils 加载 .env

# ============ LLM 配置 ============
LLM_MODEL = get_env("LLM_MODEL", "qwen-plus")  # 通义千问模型
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # OpenAI 兼容接口
LLM_API_KEY = get_env("DASHSCOPE_API_KEY", "")
LLM_TEMPERATURE = 0.1       # 低温度 → 更确定性的输出
LLM_MAX_TOKENS = 4096       # 单次最大输出 token 数


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例（通义千问 OpenAI 兼容接口）
    
    设计要点：
    - 使用 ChatOpenAI 而非直接调用 DashScope SDK
    - 因为通义千问提供了 OpenAI 兼容的 API 接口
    - 这样可以用 LangChain 的统一接口，未来切换 LLM 只需改 base_url 和 api_key
    """
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )


# ============ MongoDB 配置 ============
MONGODB_URI = get_env("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = get_env("MONGODB_DB_NAME", "erp_agent")

# ============ MCP Server 配置 ============
MCP_SERVER_URL = get_env("MCP_SERVER_URL", "http://localhost:9000")
MCP_SSE_URL = f"{MCP_SERVER_URL}/sse"  # MCP SSE 传输协议端点

# ============ 沙箱配置 ============
SANDBOX_IMAGE = get_env("SANDBOX_IMAGE", "python:3.11-slim")
SANDBOX_WORK_DIR = "/workspace"       # 沙箱内工作目录
SANDBOX_SKILLS_DIR = "/skills"        # 沙箱内技能目录
SANDBOX_MEMORIES_DIR = "/memories"    # 沙箱内记忆目录

# ============ Store 命名空间 ============
# LangGraph Store 使用命名空间隔离不同类型的跨会话数据
SKILLS_STORE_NAMESPACE = ("persisted-skills",)       # 持久化技能
PREFERENCES_STORE_NAMESPACE = ("user-preferences",)  # 用户偏好

# ============ Agent 配置 ============
MAX_MODEL_CALLS = get_env_int("MAX_MODEL_CALLS", 50)  # 单次对话最大 LLM 调用次数
MAX_TOOL_CALLS = get_env_int("MAX_TOOL_CALLS", 30)    # 单次对话最大工具调用次数
SUMMARIZATION_THRESHOLD = 0.85  # 85% 上下文窗口时触发摘要压缩

# ============ 中断配置 ============
# 这些工具被调用时会自动暂停（interrupt），等待用户审批
# 这是 HITL（Human-In-The-Loop）的核心配置
INTERRUPT_ON_TOOLS = {
    "order_create": {"allowed_decisions": ["approve", "reject"]},   # 创建订单需审批
    "order_update": {"allowed_decisions": ["approve", "reject"]},   # 修改订单需审批
}
```

**设计决策**：
- 为什么 `get_llm()` 是函数而非实例？→ 每次调用可获取新实例，避免共享状态问题
- 为什么中断只配置 `order_create` 和 `order_update`？→ 只有"写操作"需要审批，"读操作"（查询/分析）是安全的

---

## 第3章 — MCP Server 网关层

> MCP（Model Context Protocol）是一种标准协议，让 AI Agent 能以统一方式调用外部工具。本章的 MCP Server 负责把 Java ERP 的 REST API 封装为 Agent 可调用的工具。

### 3.1 `src/mcp_server/server_config.py` — ERP 后端地址配置（21行）

**作用**：定义 Java ERP 后端地址和 MCP Server 自身的监听配置。

```python
"""
MCP Server 配置模块
ERP 后端地址 + MCP 监听配置
"""
import os
from dotenv import load_dotenv

# 加载项目根目录 .env（MCP Server 独立运行，需要自己加载）
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Java ERP 后端地址 — 所有 MCP 工具最终都请求这个地址
ERP_BASE_URL = os.getenv("ERP_BASE_URL", "http://47.92.108.163:8081")

# MCP Server 监听配置
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")  # 监听所有网卡
MCP_PORT = int(os.getenv("MCP_PORT", "9000"))  # MCP 默认端口 9000

# HTTP 客户端配置
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))          # 请求超时 30 秒
HTTP_MAX_CONNECTIONS = int(os.getenv("HTTP_MAX_CONNECTIONS", "20"))  # 连接池最大 20
```

**与其他模块的关系**：被 `http_base.py` 导入使用。

---

### 3.2 `src/mcp_server/http_base.py` — httpx 异步 HTTP 客户端（97行）

**作用**：封装 httpx AsyncClient 单例，提供 GET/POST/PUT/PATCH/DELETE 方法。所有 MCP 工具都通过这个客户端与 Java ERP 通信。

```python
"""
HTTP 基础客户端模块
httpx AsyncClient 单例（连接池、超时），封装 GET/POST/PUT/PATCH/DELETE
"""
import httpx
import json
from typing import Any, Optional
from .server_config import ERP_BASE_URL, HTTP_TIMEOUT, HTTP_MAX_CONNECTIONS


class ERPHttpClient:
    """ERP 后端 HTTP 客户端单例
    
    设计要点：
    - 单例模式（__new__ 重写），全局共享一个连接池
    - 懒初始化（client 属性首次访问时才创建 AsyncClient）
    - 自动过滤 None 参数（避免发送 null 到 Java 后端）
  
        HTTP 客户端采用单例模式，因为其维护昂贵的连接池资源，全局共享可复用 TCP 连接、显著提升性能并统一超时/并发配置；而 LLM 实例不适合单例，因为不同任务需要独立的模型、温度、API Key 等参数配置，且调用本身是无状态的，按需创建更灵活、更经济。

    """
	#表示这个值可以是某种类型，也可以是 None。 Optional类型注解
    _instance: Optional['ERPHttpClient'] = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # 全局只有一个实例

    @property
    def client(self) -> httpx.AsyncClient:
        """懒初始化 AsyncClient（首次访问时创建）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=ERP_BASE_URL,          # 所有请求的基地址
                timeout=httpx.Timeout(HTTP_TIMEOUT),  # 超时 30s
                limits=httpx.Limits(
                    max_connections=HTTP_MAX_CONNECTIONS,     # 最大连接数 20
                    max_keepalive_connections=10,              # 保持活跃的连接数 10
                ),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET 请求 — 过滤 None 值参数"""
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await self.client.get(path, params=params)
        return self._handle_response(response)

    async def post(self, path: str, json_data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """POST 请求"""
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await self.client.post(path, json=json_data, params=params)
        return self._handle_response(response)

    async def put(self, path: str, json_data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """PUT 请求"""
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await self.client.put(path, json=json_data, params=params)
        return self._handle_response(response)

    async def patch(self, path: str, params: Optional[dict] = None) -> dict:
        """PATCH 请求 — 常用于状态更新"""
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        response = await self.client.patch(path, params=params)
        return self._handle_response(response)

    async def delete(self, path: str) -> dict:
        """DELETE 请求"""
        response = await self.client.delete(path)
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict:
        """统一响应处理
        
        设计要点：
        - 200 → 直接返回 JSON
        - 非200 → 包装为 {code, message, data} 格式（不抛异常）
        - 非JSON → 截断前500字符返回
        """
        try:
            data = response.json()
            if response.status_code == 200:
                return data
            else:
                return {
                    "code": response.status_code,
                    "message": f"HTTP Error: {response.status_code}",
                    "data": data,
                }
        except json.JSONDecodeError:
            return {
                "code": response.status_code,
                "message": f"Response not JSON: {response.text[:500]}",
                "data": None,
            }

    async def close(self):
        """关闭客户端（释放连接池）"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# 全局单例 — 所有 MCP 工具共享这一个客户端
erp_client = ERPHttpClient()
```

**与其他模块的关系**：被所有 `tools/*.py` 导入使用。是 MCP 工具与 Java ERP 通信的唯一出口。

---

### 3.3 `src/mcp_server/tools/suppliers_tools.py` — 供应商工具（125行）

**作用**：将 Java ERP 的供应商管理 API 封装为 5 个 MCP 工具。

```python
"""
供应商管理 MCP 工具
supplier_query / supplier_page / supplier_get / supplier_create / supplier_update_status
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client  # 导入全局 HTTP 客户端单例


def register_supplier_tools(mcp: FastMCP):
    """注册供应商管理工具到 MCP Server
    
    设计模式：闭包注册
    - 外层函数接收 mcp 实例
    - 内层函数用 @mcp.tool() 装饰器注册
    - 内层函数通过闭包访问 erp_client
    """

    @mcp.tool()
    async def supplier_query(name: str) -> str:
        """根据名称关键字搜索供应商。

        Args:
            name: 供应商名称关键字，例如"博世"、"电装"

        Returns:
            匹配的供应商列表JSON
        """
        # 调用 Java ERP: GET /api/suppliers/search?name=xxx
        result = await erp_client.get("/api/suppliers/search", params={"name": name})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def supplier_page(
        current: int = 1,
        size: int = 10,
        name: str = None,
        status: int = None,
        credit_rating: str = None,
    ) -> str:
        """分页查询供应商列表。

        Args:
            current: 当前页码，默认1
            size: 每页大小，默认10
            name: 供应商名称（可选，模糊匹配）
            status: 合作状态（可选）：1=合作中, 0=已停止
            credit_rating: 信用评级（可选）：A/B/C/D
        """
        # 注意：前端参数名是 credit_rating，Java 后端参数名是 creditRating
        # 这里做了命名转换
        params = {
            "current": current,
            "size": size,
            "name": name,
            "status": status,
            "creditRating": credit_rating,  # Java 驼峰命名
        }
        result = await erp_client.get("/api/suppliers/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def supplier_get(id: int) -> str:
        """获取单个供应商的详细信息。"""
        result = await erp_client.get(f"/api/suppliers/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def supplier_create(
        supplier_code: str, name: str,
        contact_person: str = None, phone: str = None,
        email: str = None, address: str = None,
        credit_rating: str = None, status: int = 1,
    ) -> str:
        """创建新供应商。"""
        data = {
            "supplierCode": supplier_code, "name": name,
            "contactPerson": contact_person, "phone": phone,
            "email": email, "address": address,
            "creditRating": credit_rating, "status": status,
        }
        data = {k: v for k, v in data.items() if v is not None}  # 移除 None
        result = await erp_client.post("/api/suppliers/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def supplier_update_status(id: int, status: int) -> str:
        """更新供应商合作状态。"""
        result = await erp_client.patch(
            f"/api/suppliers/update-status/{id}", params={"status": status}
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
```

**工具清单**：
| 工具名 | HTTP 方法 | Java ERP 路径 | 用途 |
|--------|-----------|---------------|------|
| `supplier_query` | GET | `/api/suppliers/search` | 按名称搜索 |
| `supplier_page` | GET | `/api/suppliers/page` | 分页查询 |
| `supplier_get` | GET | `/api/suppliers/get/{id}` | 获取详情 |
| `supplier_create` | POST | `/api/suppliers/create` | 创建供应商 |
| `supplier_update_status` | PATCH | `/api/suppliers/update-status/{id}` | 更新状态 |

---

### 3.4 `src/mcp_server/tools/parts_tools.py` — 零部件工具（130行）

**作用**：5 个零部件管理 MCP 工具。模式与供应商工具完全相同。

```python
"""
产品/零部件管理 MCP 工具
part_query / part_search / part_by_supplier / part_page / part_create
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client


def register_parts_tools(mcp: FastMCP):
    """注册零部件管理工具到 MCP Server"""

    @mcp.tool()
    async def part_query(id: int) -> str:
        """获取单个零部件的详细信息。
        Args:
            id: 零部件ID
        Returns:
            零部件详细信息JSON，包含 partCode, name, model, specification,
            unit, purchasePrice, suggestedRetailPrice, stockWarningValue 等
        """
        result = await erp_client.get(f"/api/parts/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_search(name: str) -> str:
        """根据名称关键字搜索零部件。
        Args:
            name: 零件名称关键字，例如"火花塞"、"刹车片"、"滤芯"
        """
        result = await erp_client.get("/api/parts/search", params={"name": name})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_by_supplier(supplier_id: int) -> str:
        """获取指定供应商的所有产品列表。
        Args:
            supplier_id: 供应商ID
        """
        result = await erp_client.get(f"/api/parts/supplier/{supplier_id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_page(current: int = 1, size: int = 10,
                        name: str = None, category: str = None,
                        supplier_id: int = None) -> str:
        """分页查询零部件列表。"""
        params = {"current": current, "size": size, "name": name,
                  "category": category, "supplierId": supplier_id}
        result = await erp_client.get("/api/parts/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def part_create(part_code: str, name: str, purchase_price: float,
                          model: str = None, specification: str = None,
                          unit: str = None, suggested_retail_price: float = None,
                          stock_warning_value: int = None, supplier_id: int = None,
                          category: str = None, description: str = None) -> str:
        """创建新零部件。"""
        data = {"partCode": part_code, "name": name, "purchasePrice": purchase_price,
                "model": model, "specification": specification, "unit": unit,
                "suggestedRetailPrice": suggested_retail_price,
                "stockWarningValue": stock_warning_value,
                "supplierId": supplier_id, "category": category, "description": description}
        data = {k: v for k, v in data.items() if v is not None}
        result = await erp_client.post("/api/parts/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)
```

---

### 3.5 `src/mcp_server/tools/order_tools.py` — 订单工具（169行）

**作用**：7 个采购订单管理 MCP 工具。这是最复杂的工具组，因为订单涉及创建、修改、状态变更等写操作。

```python
"""
采购订单管理 MCP 工具
order_create / order_update / order_page / order_get / order_search_details / order_statistics / order_update_status
"""
import json
from typing import Optional
from fastmcp import FastMCP
from ..http_base import erp_client


def register_order_tools(mcp: FastMCP):
    """注册采购订单管理工具到 MCP Server"""

    @mcp.tool()
    async def order_create(order_data: str) -> str:
        """创建采购订单。

        Args:
            order_data: 订单数据JSON字符串，格式：
                {
                    "orderNumber": "PO20260101001",  // 必填，订单编号
                    "totalAmount": 1000.0,           // 总金额
                    "status": 0,                     // 0=待审核,1=已审核,2=已发货,3=已收货,4=已完成
                    "orderDetail": [                 // 订单明细列表
                        {
                            "partId": 1,            // 必填，零部件ID
                            "quantity": 100,        // 必填，数量>=1
                            "unitPrice": 25.5,      // 必填，单价
                        }
                    ]
                }
        """
        try:
            data = json.loads(order_data) if isinstance(order_data, str) else order_data
        except json.JSONDecodeError as e:
            return json.dumps({"code": 400, "message": f"JSON解析失败: {e}"}, ensure_ascii=False)
        result = await erp_client.post("/api/orders/create", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_update(id: int, order_data: str) -> str:
        """更新采购订单。"""
        try:
            data = json.loads(order_data) if isinstance(order_data, str) else order_data
        except json.JSONDecodeError as e:
            return json.dumps({"code": 400, "message": f"JSON解析失败: {e}"}, ensure_ascii=False)
        result = await erp_client.put(f"/api/orders/update/{id}", json_data=data)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_page(current: int = 1, size: int = 10,
                         order_number: str = None, status: int = None,
                         start_date: str = None, end_date: str = None) -> str:
        """分页查询采购订单列表。"""
        params = {"current": current, "size": size, "orderNumber": order_number,
                  "status": status, "startDate": start_date, "endDate": end_date}
        result = await erp_client.get("/api/orders/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_get(id: int) -> str:
        """获取单个采购订单的详细信息（含订单明细）。"""
        result = await erp_client.get(f"/api/orders/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_search_details(part_name: str = None,
                                   start_date: str = None, end_date: str = None) -> str:
        """搜索订单明细，支持按零部件名称和时间范围过滤。"""
        params = {"partName": part_name, "startDate": start_date, "endDate": end_date}
        result = await erp_client.get("/api/orders/search-details", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_statistics(start_date: str = None, end_date: str = None) -> str:
        """获取采购统计数据。"""
        params = {"startDate": start_date, "endDate": end_date}
        result = await erp_client.get("/api/orders/statistics", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def order_update_status(id: int, status: int) -> str:
        """更新订单状态。0=待审核,1=已审核,2=已发货,3=已收货,4=已完成"""
        result = await erp_client.patch(
            f"/api/orders/update-status/{id}", params={"status": status}
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
```

---

### 3.6 `src/mcp_server/tools/inventory_tools.py` — 库存工具（114行）

**作用**：6 个库存管理 MCP 工具。

```python
"""
库存管理 MCP 工具
inventory_warning / inventory_page / inventory_check / inventory_inbound / inventory_outbound / inventory_get
"""
import json
from fastmcp import FastMCP
from ..http_base import erp_client


def register_inventory_tools(mcp: FastMCP):
    """注册库存管理工具到 MCP Server"""

    @mcp.tool()
    async def inventory_warning() -> str:
        """获取库存预警列表，返回当前库存量低于安全库存的所有零部件。"""
        result = await erp_client.get("/api/inventory/warning")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_page(current: int = 1, size: int = 10,
                             part_name: str = None, warehouse_location: str = None) -> str:
        """分页查询库存列表。"""
        params = {"current": current, "size": size,
                  "partName": part_name, "warehouseLocation": warehouse_location}
        result = await erp_client.get("/api/inventory/page", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_check() -> str:
        """执行库存盘点，返回库存总览统计。"""
        result = await erp_client.get("/api/inventory/check")
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_inbound(part_id: int, quantity: int,
                                warehouse_location: str = None) -> str:
        """执行入库操作。"""
        params = {"partId": part_id, "quantity": quantity, "warehouseLocation": warehouse_location}
        result = await erp_client.post("/api/inventory/inbound", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_outbound(part_id: int, quantity: int) -> str:
        """执行出库操作。"""
        params = {"partId": part_id, "quantity": quantity}
        result = await erp_client.post("/api/inventory/outbound", params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def inventory_get(id: int) -> str:
        """获取单条库存记录详情。"""
        result = await erp_client.get(f"/api/inventory/get/{id}")
        return json.dumps(result, ensure_ascii=False, indent=2)
```

---

### 3.7 `src/mcp_server/server_main.py` — FastMCP 入口（34行）

**作用**：创建 FastMCP 实例，注册所有工具，以 SSE 传输协议启动。

```python
"""
MCP Server 入口
FastMCP 实例创建，注册所有 tools，SSE 传输协议
"""
import sys
import os

# 确保项目根目录在 path 中（MCP Server 可能独立启动）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastmcp import FastMCP
from src.mcp_server.server_config import MCP_HOST, MCP_PORT
from src.mcp_server.tools.suppliers_tools import register_supplier_tools
from src.mcp_server.tools.parts_tools import register_parts_tools
from src.mcp_server.tools.order_tools import register_order_tools
from src.mcp_server.tools.inventory_tools import register_inventory_tools

# 创建 MCP Server 实例
mcp = FastMCP(
    name="ERP-Procurement-MCP",
    instructions="摩托车零部件采购管理系统 MCP 网关，提供供应商、零部件、订单、库存查询和管理能力。",
)

# 注册所有工具（共 23 个）
register_supplier_tools(mcp)     # 5 个供应商工具
register_parts_tools(mcp)        # 5 个零部件工具
register_order_tools(mcp)        # 7 个订单工具
register_inventory_tools(mcp)    # 6 个库存工具


if __name__ == "__main__":
    print(f"🚀 Starting MCP Server on {MCP_HOST}:{MCP_PORT} (SSE transport)")
    # 以 SSE 传输协议启动，Agent 通过 http://localhost:9000/sse 连接
    mcp.run(transport="sse", host=MCP_HOST, port=MCP_PORT)
```

**MCP 协议工作原理总结**：
1. MCP Server 启动后监听 `:9000/sse`，提供 SSE 连接
2. Agent 的 `mcp_client.py` 通过 `MultiServerMCPClient` 连接 SSE
3. 连接建立后，Agent 获取所有 23 个工具的 schema（名称、参数、描述）
4. Agent 调用工具时，MCP Server 执行对应的 async 函数 → HTTP 请求 Java ERP → 返回 JSON 结果

---

## 第4章 — Agent 工具层

> 除了 MCP 提供的 23 个 ERP 工具外，Agent 还有 9 个自定义工具：图表生成（沙箱内）、文档生成（沙箱内）、网络搜索、URL 抓取、Skill 安装（沙箱隔离流程）、人工介入、技能分配、沙箱文件下载、沙箱文件列表。
> 
> ⚠️ **核心安全原则**：所有涉及代码执行和文件生成的操作（图表/文档/Skill安装）都必须在 Docker 沙箱内进行，宿主机只运行 Agent 框架本身。

### 4.1 `src/agent/tools/mcp_client.py` — MCP 工具加载（127行）

**作用**：连接 MCP Server，获取所有 ERP 工具，支持重试、缓存、优雅降级。

```python
"""
MCP 工具加载模块
使用 langchain-mcp-adapters 连接 MCP Server（SSE模式），获取所有 ERP 工具

生产级实现：
- 连接重试（指数退避）
- 连接健康检查
- 优雅降级（MCP不可用时返回空工具列表，Agent仍可对话）
"""
import asyncio
import time
from typing import List
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from ..config import MCP_SERVER_URL, MCP_SSE_URL
from ..log_utils import mcp_logger

# 重试配置
MAX_RETRIES = 3                # 最多重试 3 次
RETRY_BASE_DELAY = 1.0         # 首次重试等待 1 秒
RETRY_BACKOFF_FACTOR = 2.0     # 指数退避因子（1s → 2s → 4s）

# 缓存（避免重复连接）
_cached_tools: List[BaseTool] | None = None
_cache_time: float = 0
CACHE_TTL = 300  # 5分钟缓存TTL


async def load_mcp_tools(force_refresh: bool = False) -> List[BaseTool]:
    """
    异步加载 MCP 工具列表（带重试和缓存）
    
    流程：
    1. 检查缓存 → 命中则直接返回
    2. 连接 MCP Server（SSE 协议）
    3. 获取工具列表
    4. 缓存结果
    5. 失败时指数退避重试
    6. 全部失败时返回空列表（优雅降级）
    虽然 SSE 本身是服务器到客户端的单向流，但 MCP 巧妙地利用“SSE 流接收 + HTTP POST 发送”的组合实现了双向消息交换。这种设计天然适配 HTTP 基础设施（如代理、负载均衡、防火墙），便于集成认证和监控
    """
    global _cached_tools, _cache_time

    # 检查缓存
    if not force_refresh and _cached_tools is not None:
        if time.time() - _cache_time < CACHE_TTL:
            return _cached_tools

    mcp_logger.info(f"Connecting to MCP Server: {MCP_SSE_URL}")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # MultiServerMCPClient 是 langchain-mcp-adapters 提供的客户端
            # 它通过 SSE 连接 MCP Server，自动获取所有工具的 schema
            client = MultiServerMCPClient(
                {
                    "erp": {           # 服务器名称（可配置多个）
                        "url": MCP_SSE_URL,    # SSE 端点
                        "transport": "sse",    # 传输协议
                    }
                }
            )
            tools = await client.get_tools()  # 获取所有工具

            if tools:
                _cached_tools = tools
                _cache_time = time.time()
                mcp_logger.info(
                    f"Loaded {len(tools)} MCP tools: {[t.name for t in tools]}"
                )
                return tools
            else:
                mcp_logger.warning("MCP Server returned 0 tools")
                return []

        except Exception as e:
            last_error = e
            delay = RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            mcp_logger.warning(
                f"MCP connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)

    # 全部失败 → 优雅降级（Agent 仍可对话，只是没有 ERP 工具）
    mcp_logger.error(
        f"All {MAX_RETRIES} MCP connection attempts failed. "
        f"Agent will operate without ERP tools."
    )
    return []


def load_mcp_tools_sync(force_refresh: bool = False) -> List[BaseTool]:
    """同步包装：加载 MCP 工具列表
    
    处理各种事件循环状态：
    - 无事件循环 → asyncio.run()
    - 有运行中的事件循环 → ThreadPoolExecutor + asyncio.run()
    在异步事件中必须先创建同步循环
    在异步上下文中必须使用同步包装器加线程池，核心原因是 Python 的 asyncio.run() 强制要求当前线程没有正在运行的事件循环，否则会直接抛出 RuntimeError；而你的代码可能既会在纯同步脚本中直接运行，也会在 FastAPI 等异步框架的启动阶段被调用，后者已经有一个正在运行的事件循环。为了兼容这两种场景，你的 load_mcp_tools_sync 函数先检测当前线程是否有活跃的事件循环：如果没有，就直接用 asyncio.run() 执行异步协程；如果有，则通过 ThreadPoolExecutor 在新线程中执行 asyncio.run()，因为每个线程可以独立拥有自己的事件循环，从而避免嵌套冲突。这种设计既保证了代码的健壮性和可移植性，又通过线程隔离确保了异步任务的正确执行，是处理"同步包装异步函数"场景的标准做法。
    """
    global _cached_tools, _cache_time
    if not force_refresh and _cached_tools is not None:
        if time.time() - _cache_time < CACHE_TTL:
            return _cached_tools

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
# 检测当前线程是否已经有正在运行的事件循环
# asyncio.get_running_loop() 在有事件循环时返回它，没有时会抛出 RuntimeError
if loop and loop.is_running():
    # 情况1：当前线程已经有事件循环在运行了（比如 FastAPI 启动时）
    # 此时不能直接调用 asyncio.run()，因为它会尝试创建新的事件循环并报错
    
    # 导入线程池模块（通常放在顶部，这里为了演示放在此处）
    import concurrent.futures
    
    # 创建一个线程池，最多同时运行 1 个线程
    # 使用 with 语句确保线程池用完后自动关闭，释放资源
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        # pool.submit() 将任务提交到线程池中异步执行
        # 它会在新线程中执行 asyncio.run(load_mcp_tools(force_refresh))
        # 新线程里没有运行中的事件循环，所以 asyncio.run() 可以安全执行
        # 这样就避免了"在已有事件循环中再次调用 asyncio.run()"的冲突
        future = pool.submit(asyncio.run, load_mcp_tools(force_refresh))
        
        # future.result() 会阻塞当前线程，等待新线程中的任务执行完毕
        # timeout=30 表示最多等待 30 秒，超时则抛出 TimeoutError
        # 返回值就是 load_mcp_tools() 执行完毕后的结果（工具列表）
        return future.result(timeout=30)
else:
    # 情况2：当前线程没有运行中的事件循环（比如直接运行 Python 脚本）
    # 此时可以安全地调用 asyncio.run()
    # 它会创建一个新的事件循环，执行 load_mcp_tools()，然后自动关闭循环
    # 这是最简洁的方式，适合纯同步环境
    return asyncio.run(load_mcp_tools(force_refresh))


def invalidate_cache():
    """清除工具缓存（MCP Server 重启后调用）"""
    global _cached_tools, _cache_time
    _cached_tools = None
    _cache_time = 0
    mcp_logger.info("MCP tools cache invalidated")
```

---

### 4.2 `src/agent/tools/chart_generator.py` — 26种图表生成（322行，沙箱内执行）

**作用**：单一 `@tool generate_chart` 支持 26 种图表类型，在 **Docker 沙箱内** 用 matplotlib 生成 PNG 图片。

**核心设计（Harness 思想）**：
- 所有图表必须在 Docker 沙箱内生成（`/workspace/charts/`）
- 用户需要下载时，通过 `download_sandbox_file` 工具从沙箱提取到本地
- 沙箱不可用时返回错误，**不回退到宿主机执行**

```python
@tool
def generate_chart(
    chart_type: str,
    data: str,
    title: str = "数据图表",
    x_field: str = "label",
    y_field: str = "value",
    series_field: str = "",
) -> str:
    """在沙箱中生成数据可视化图表（支持26种类型）。

    Args:
        chart_type: 图表类型，如 bar/pie/line/scatter 等
        data: 数据JSON字符串。格式: [{"label":"名称","value":数值}, ...]
        ...
    Returns:
        图表沙箱路径，或错误信息
    """
    # 解析数据
    data_list = json.loads(data) if isinstance(data, str) else data

    # 获取沙箱实例（通过全局 holder）
    sandbox = get_sandbox()
    if sandbox is None:
        return "错误: 沙箱不可用。请确保 Docker 沙箱容器已启动。"

    # 沙箱内路径
    charts_dir = "/workspace/charts"
    output_path = f"{charts_dir}/chart_{chart_type}_{timestamp}.png"

    # 写入脚本和参数到沙箱
    sandbox.write_file(params_path, json.dumps(params))
    sandbox.write_file(script_path, CHART_SCRIPT)

    # 安装依赖（首次，后续复用 Docker 缓存）
    sandbox.execute("pip install -q matplotlib numpy 2>/dev/null || true", timeout=60)

    # ⚠️ 在沙箱内执行 matplotlib 绘图（而非宿主机 subprocess）
    result = sandbox.execute(f"python {script_path} {params_path}", timeout=30)

    if result.exit_code == 0 and sandbox.file_exists(output_path):
        file_size = len(sandbox.read_file_bytes(output_path))
        return (
            f"✅ 图表已生成!\n"
            f"沙箱路径: {output_path}\n"
            f"💡 如需下载到本地，请使用 download_sandbox_file 工具"
        )
```

**架构升级**：旧版用 `subprocess.run(["python", script, ...])` 在宿主机执行 → 新版用 `sandbox.execute()` 在 Docker 沙箱内执行。

| 对比 | 旧版（已废弃） | 新版（当前） |
|------|---------------|-------------|
| 执行位置 | 宿主机 subprocess | Docker 沙箱内 |
| 文件存储 | 宿主机 `src/download/` | 沙箱 `/workspace/charts/` |
| 依赖安装 | 宿主机 pip | 沙箱内 `sandbox.execute("pip install ...")` |
| 失败降级 | 无 | 沙箱不可用时返回错误 |
| 下载方式 | 直接返回 URL | 需用户确认后调用 `download_sandbox_file` |

---

### 4.3 `src/agent/tools/web_search.py` — 网络搜索（68行）

**作用**：使用通义千问 API 的搜索增强能力实现联网搜索。

```python
"""
Web 搜索工具
使用通义千问 API 的搜索增强能力实现网络搜索
"""
import os
import httpx
from langchain_core.tools import tool
from ..log_utils import agent_logger
from ..env_utils import get_env


@tool
def web_search(query: str) -> str:
    """搜索互联网获取实时信息。

    Args:
        query: 搜索查询内容，例如"摩托车火花塞市场价格趋势 2026"
    Returns:
        搜索结果摘要文本
    """
    api_key = get_env("DASHSCOPE_API_KEY", "")
    if not api_key:
        return "错误: 未配置 DASHSCOPE_API_KEY，无法执行网络搜索"

    try:
        # 核心：使用通义千问的 enable_search=True 参数开启联网搜索
        response = httpx.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "qwen-plus",
                "messages": [
                    {"role": "system", "content": "你是一个搜索助手。请根据用户的查询，提供准确、有用的信息摘要。"},
                    {"role": "user", "content": f"请搜索并总结以下信息：{query}"}
                ],
                "enable_search": True,    # ⚡ 关键参数：开启联网搜索
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content
        else:
            error = response.json().get("error", {}).get("message", str(response.status_code))
            return f"搜索失败: {error}"
    except httpx.TimeoutException:
        return "搜索超时，请稍后重试"
    except Exception as e:
        return f"搜索异常: {str(e)}"
```

---

### 4.4 `src/agent/tools/web_fetch.py` — URL抓取 + Skill安装（390行，沙箱隔离流程）

**作用**：两个工具——`web_fetch` 获取 URL 内容，`install_skill` 下载并安装 Skill（沙箱安全隔离流程）。

**`install_skill` 安全流程**：
```
下载 → 内存解压 → 上传沙箱 /tmp/ 验证 SKILL.md
    ↓ 通过                          ↓ 失败
安装到宿主机 src/skills/           清理沙箱临时文件
同步到沙箱 /skills/                返回错误（不影响宿主）
安装依赖（沙箱内 pip install）
```

```python
"""
Web 抓取 & Skill 下载工具
- web_fetch: 获取任意 URL 的文本内容（HTML→纯文本 / JSON / Markdown）
- install_skill: 从 URL 下载完整 Skill 文件夹（含 SKILL.md + 脚本 + 依赖）并安装。

Skill 标准结构：
  skill-name/
    SKILL.md          # 技能定义（必须有）
    scraper.py        # 脚本文件（可选）
    requirements.txt  # 依赖（可选）
    assets/           # 资源文件（可选）
"""
import os
import re
import io
import zipfile
import tarfile
import httpx
import shutil
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

# Skills 目录：项目根/src/skills
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "src" / "skills"


def _strip_html(html: str) -> str:
    """简易 HTML → 纯文本（去标签、合并空白）"""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool
def web_fetch(url: str, max_chars: int = 8000) -> str:
    """获取指定 URL 的网页内容（转为纯文本）。

    可用于：
    - 查看技术文档、API 说明
    - 获取 Skill 文件内容
    - 阅读在线资源

    Args:
        url: 完整的 HTTP/HTTPS 地址
        max_chars: 返回内容最大字符数（默认8000）

    Returns:
        网页文本内容或错误信息
    """
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Downloader)"},
        )

        if response.status_code != 200:
            return f"请求失败: HTTP {response.status_code}"

        content_type = response.headers.get("content-type", "")
        text = response.text

        # HTML → 纯文本
        if "text/html" in content_type:
            text = _strip_html(text)

        # 截断
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [内容已截断，共 {len(response.text)} 字符]"

        agent_logger.info(f"web_fetch: {url} ({len(text)} chars)")
        return text

    except httpx.TimeoutException:
        return f"请求超时: {url}"
    except Exception as e:
        agent_logger.error(f"web_fetch error: {e}")
        return f"获取失败: {str(e)}"


# ============================================================
# Skill 安装（沙箱安全隔离）
# 流程图：下载 → 沙箱验证 → 通过 → 安装到正式环境
#         ↓ 失败
#       清理沙箱临时文件 + 返回错误
# ============================================================
def _extract_archive_to_memory(data: bytes, url: str, content_type: str) -> dict[str, bytes]:
    """
    将压缩包解压到内存字典 {相对路径: 字节内容}。
    支持 ZIP 和 TAR.GZ 格式。
    """
    # 初始化结果字典，用于存储解压后的文件路径和内容
    result: dict[str, bytes] = {}

    try:
        # 检查 URL 是否以 .zip 结尾或 content-type 包含 zip
        if url.lower().endswith(".zip") or "zip" in content_type:
            # 使用 io.BytesIO 将字节数据转为内存中的文件对象
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # 遍历 ZIP 包中的所有成员（文件/文件夹）
                for member in zf.namelist():
                    # 跳过目录（以/结尾）、__MACOSX 系统文件夹、隐藏文件（以.开头）
                    if member.endswith("/") or "/__MACOSX/" in member or member.startswith("."):
                        continue
                    # 按第一个斜杠分割路径，获取相对路径
                    parts = member.split("/", 1)
                    # 如果有多级目录，取第二部分作为相对路径；否则直接用文件名
                    rel_path = parts[1] if len(parts) > 1 else parts[0]
                    if rel_path:
                        # 将文件内容读入内存，存入结果字典
                        result[rel_path] = zf.read(member)
        else:
            # 处理 tar.gz 格式
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                # 遍历 tar 包中的所有成员
                for member in tf.getmembers():
                    # 只处理文件（不是目录），且文件名不以.开头
                    if member.isfile() and not member.name.startswith("."):
                        # 按第一个斜杠分割，获取相对路径
                        parts = member.name.split("/", 1)
                        rel_path = parts[1] if len(parts) > 1 else parts[0]
                        if rel_path:
                            # 提取文件内容
                            fobj = tf.extractfile(member)
                            if fobj:
                                result[rel_path] = fobj.read()
    except (zipfile.BadZipFile, tarfile.TarError):
        # 如果压缩包损坏或格式不对，不做任何处理，返回空字典
        pass

    # 返回解压后的文件字典
    return result


def _validate_skill_in_sandbox(sandbox, skill_name: str, sandbox_skill_dir: str) -> tuple[bool, str, list[str]]:
    """
    在沙箱中验证技能文件完整性（严格模式：方案一 YAML 严格解析 + 方案二危险代码扫描）。

    验证项目：
    1. SKILL.md 文件存在性
    2. YAML frontmatter 合法解析（yaml.safe_load）
    3. 必需字段 name 的非空校验
    4. 可选字段类型校验（version, description）
    5. name 字段路径安全性校验（[\\w\\-\\.]+）
    6. Python 文件危险代码扫描（eval/exec/subprocess/pickle 等 11 种模式）
    7. 路径穿越攻击检测（..）
    8. 文件大小 DoS 防护（10MB 上限）
    """
    # 1. 检查 SKILL.md 是否存在
    has_sk = sandbox.execute(f"test -f '{sandbox_skill_dir}/SKILL.md' && echo YES || echo NO")
    if has_sk.exit_code != 0 or "YES" not in has_sk.output:
        return False, "SKILL.md 未找到，技能格式无效", []

    # 2. 读取完整内容 + 3. 校验 YAML frontmatter
    read_sk = sandbox.execute(f"cat '{sandbox_skill_dir}/SKILL.md'")
    content = read_sk.output
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.search(frontmatter_pattern, content, re.DOTALL)
    if not match:
        return False, "SKILL.md 缺少有效的 YAML frontmatter（必须用 --- 包裹）", []

    # 4. 使用 yaml 库严格解析 + 字段校验
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        return False, "YAML frontmatter 格式错误（必须是键值对）", []
    if "name" not in metadata or not metadata["name"] or not isinstance(metadata["name"], str):
        return False, "SKILL.md 'name' 字段必须是非空字符串", []
    if not re.match(r'^[\w\-\.]+$', metadata["name"]):
        return False, f"SKILL.md 'name' 字段包含非法字符: {metadata['name']}", []

    # 5. 安全扫描：检查 .py 文件中的危险模式（方案二部分）
    py_files = sandbox.execute(f"find '{sandbox_skill_dir}' -name '*.py' -type f")
    for py_file in py_files.output.strip().split('\n'):
        content = sandbox.execute(f"cat '{py_file}'").output
        for pattern, warning in _DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                agent_logger.warning(f"Security risk in {py_file}: {warning}")

    # 6. 路径穿越检测 + 7. 文件大小检查
    ls_result = sandbox.execute(f"find '{sandbox_skill_dir}' -type f | sort")
    files = [f.strip() for f in ls_result.output.strip().split("\n") if f.strip()]
    for f in files:
        if '..' in f:
            return False, f"检测到路径穿越攻击: {f}", []

    return True, "", files


def _install_from_sandbox_to_host(sandbox, sandbox_skill_dir: str, host_skill_dir: Path, files: list[str]) -> list[str]:
    """
    从沙箱读取验证通过的文件，写入宿主机 skills 目录。
    返回已安装的文件列表。
    """
    # 初始化已安装文件列表
    installed = []
    # 遍历所有需要从沙箱复制的文件
    for remote_path in files:
        try:
            # 从沙箱读取文件内容（字节）
            content = sandbox.read_file_bytes(remote_path)
            # 计算相对于沙箱技能目录的相对路径
            rel = remote_path.replace(sandbox_skill_dir, "").lstrip("/")
            # 构建宿主机上的目标文件路径
            target = host_skill_dir / rel
            # 创建目标文件所在的目录（如果不存在）
            target.parent.mkdir(parents=True, exist_ok=True)
            # 将内容写入宿主机文件
            target.write_bytes(content)
            # 记录已安装的文件名
            installed.append(rel)
        except Exception as e:
            # 如果复制失败，记录警告日志但继续处理其他文件
            agent_logger.warning(f"Failed to copy {remote_path} from sandbox: {e}")
    return installed


@tool
def install_skill(url: str, skill_name: str = "") -> str:
    """从 URL 下载并安装完整 Skill（沙箱安全隔离流程）。

    安全流程：
    1. 下载到内存
    2. 上传到沙箱 /tmp/ 验证
    3. 在沙箱中解压并校验 SKILL.md 完整性
    4. 校验通过 → 从沙箱复制到宿主机 src/skills/
    5. 校验失败 → 清理沙箱临时文件

    支持四种来源：
    1. GitHub 仓库 ZIP（如 https://github.com/user/repo/archive/refs/heads/main.zip）
    2. 任意 ZIP/TAR.GZ 压缩包（包含 SKILL.md 的文件夹）
    3. 单个 SKILL.md 文件 URL
    4. GitHub 仓库页面（自动转换为 ZIP 下载）

    标准 Skill 文件夹结构：
      skill-name/
        SKILL.md          # 技能定义（必须）
        *.py              # 脚本（可选）
        requirements.txt  # 依赖（可选）

    Args:
        url: Skill 的下载地址（ZIP 压缩包、GitHub 仓库、或 .md 文件）
        skill_name: 技能名称。为空则从 URL 自动提取。

    Returns:
        安装结果说明（含安装路径和文件列表）
    """
    # 验证 URL 协议是否合法（只支持 HTTP 和 HTTPS）
    if not url.startswith(("http://", "https://")):
        return "错误: URL 必须以 http:// 或 https:// 开头"

    # 标准化 GitHub URL，将仓库页面转为 ZIP 下载链接
    url = _normalize_github_url(url)
    # 如果未指定技能名称，从 URL 自动提取
    if not skill_name:
        skill_name = _extract_skill_name(url)
    # 将技能名称中的非法字符替换为下划线，确保文件系统安全
    skill_name = re.sub(r"[^\w\-]", "_", skill_name)

    # 获取沙箱实例（安全隔离环境）
    from ..backends.sandbox_holder import get_sandbox
    sandbox = get_sandbox()

    try:
        # Step 1: 下载文件到内存
        response = httpx.get(
            url,
            follow_redirects=True,  # 自动跟随重定向
            timeout=30,              # 30秒超时
            headers={"User-Agent": "ERP-Agent/1.0 (Skill Installer)"},  # 设置 User-Agent
        )
        # 检查 HTTP 响应状态码
        if response.status_code != 200:
            return f"下载失败: HTTP {response.status_code}"
        # 获取响应头中的 content-type
        content_type = response.headers.get("content-type", "")
        # 检查下载内容是否为空
        if len(response.content) == 0:
            return "错误: 下载内容为空"

        # 检查沙箱是否可用
        if sandbox is None:
            return "错误: 沙箱不可用，无法安全安装 Skill"

        # Step 2: 在 Python 中解压，获取文件映射
        # 在沙箱中创建临时目录用于验证
        sandbox_tmp = f"/tmp/_skill_install_{skill_name}"

        # 判断是否为压缩包格式
        if _is_archive(url, content_type):
            # 解压到内存字典
            files_dict = _extract_archive_to_memory(response.content, url, content_type)
        else:
            # 单文件（SKILL.md），直接保存为字节
            files_dict = {"SKILL.md": response.text.encode("utf-8")}

        # 如果没有提取到任何文件，清理沙箱临时目录并报错
        if not files_dict:
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 压缩包中未找到有效文件"

        # 找到 SKILL.md 所在的目录前缀（用于剥离顶层目录）
        skill_prefix = ""
        for path in files_dict:
            if path.endswith("SKILL.md"):
                # 如果路径包含斜杠，取目录部分作为前缀
                parts = path.split("/")
                if len(parts) > 1:
                    skill_prefix = "/".join(parts[:-1]) + "/"
                break
        else:
            # 如果循环结束都没找到 SKILL.md
            sandbox.execute(f"rm -rf {sandbox_tmp} 2>/dev/null || true")
            return "错误: 未找到 SKILL.md，安装取消"

        # Step 3: 上传文件到沙箱验证
        sandbox.execute(f"mkdir -p {sandbox_tmp}/skill")
        for rel_path, content in files_dict.items():
            clean_path = rel_path[len(skill_prefix):] if rel_path.startswith(skill_prefix) else rel_path
            if not clean_path:
                continue
            sandbox.write_file(f"{sandbox_tmp}/skill/{clean_path}", content)

        # Step 4: 在沙箱中验证文件完整性
        valid, err_msg, sandbox_files = _validate_skill_in_sandbox(sandbox, skill_name, f"{sandbox_tmp}/skill")
        if not valid:
            # 验证失败，清理沙箱临时文件
            sandbox.execute(f"rm -rf {sandbox_tmp}")
            return f"沙箱验证失败: {err_msg}（已清理沙箱临时文件，未影响宿主机）"

        # Step 5: 验证通过 → 从沙箱复制到宿主机 + 沙箱正式目录
        sandbox_verify_dir = f"{sandbox_tmp}/skill"
        host_skills_dir = Path(SKILLS_DIR)
        host_skills_dir.mkdir(parents=True, exist_ok=True)
        host_target = host_skills_dir / skill_name

        installed = _install_from_sandbox_to_host(sandbox, sandbox_verify_dir, host_target, sandbox_files)

        # 同步写入沙箱正式技能目录（用于后续执行）
        scope = "procurement"
        for rel in installed:
            remote_target = f"/skills/{scope}/{skill_name}/{rel}"
            try:
                sandbox.write_file(remote_target, sandbox.read_file_bytes(f"{sandbox_verify_dir}/{rel}"))
            except Exception as e:
                agent_logger.warning(f"Failed to write to sandbox skills dir: {e}")

        # 安装依赖（在沙箱内执行 pip install -r requirements.txt）
        _install_dependencies(host_target)

        # 清理沙箱临时文件（释放临时空间）
        sandbox.execute(f"rm -rf {sandbox_tmp}")

        # 记录安装日志
        agent_logger.info(
            f"Skill installed (sandbox-verified): {skill_name} ({len(installed)} files)"
        )
        # 返回成功信息，包含技能名称、路径、文件数量和列表
        return (
            f"✅ Skill 安装成功！（沙箱安全验证通过）\n"
            f"名称: {skill_name}\n"
            f"路径: {host_target}\n"
            f"文件数: {len(installed)}\n"
            f"文件列表:\n" +
            "\n".join(f"  - {f}" for f in installed[:20]) +  # 只显示前20个文件
            (f"\n  ... 共 {len(installed)} 个文件" if len(installed) > 20 else "") +
            f"\n来源: {url}\n\n"
            f"该 Skill 已通过沙箱安全验证，现已安装到正式环境。"
        )

    except httpx.TimeoutException:
        # 处理下载超时异常
        return f"下载超时: {url}"
    except Exception as e:
        # 处理其他所有异常，记录错误日志
        agent_logger.error(f"install_skill error: {e}")
        # 尝试清理沙箱临时文件
        if sandbox:
            try:
                sandbox.execute(f"rm -rf /tmp/_skill_install_{skill_name} 2>/dev/null || true")
            except Exception:
                pass
        return f"安装失败: {str(e)}"


def _normalize_github_url(url: str) -> str:
    """将 GitHub 仓库页面 URL 自动转换为 ZIP 下载链接"""
    # 匹配 GitHub 仓库 URL 的正则表达式
    # 格式: https://github.com/owner/repo 或 https://github.com/owner/repo/tree/branch/path
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+)(/.+))?",
        url,
    )
    if match:
        # 提取所有者、仓库名和分支
        owner, repo = match.group(1), match.group(2)
        branch = match.group(3) or "main"  # 默认使用 main 分支
        # 如果 URL 本身不是压缩包链接，转换为 ZIP 下载链接
        if not url.endswith((".zip", ".tar.gz", ".tgz")):
            return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    return url  # 不是 GitHub 仓库 URL，原样返回


def _extract_skill_name(url: str) -> str:
    """从 URL 提取 skill 名称"""
    # 去掉查询参数（?后面的部分）
    path_part = url.split("?")[0].rstrip("/")

    # 如果是 GitHub 仓库，提取仓库名
    match = re.search(r"github\.com/[^/]+/([^/]+)", path_part)
    if match:
        return match.group(1).replace(".git", "")  # 移除 .git 后缀

    # 否则取路径的最后一部分作为文件名
    filename = path_part.split("/")[-1]
    # 移除常见的压缩包和文档扩展名
    name = re.sub(r"\.(zip|tar\.gz|tgz|md|txt|markdown)$", "", filename, flags=re.IGNORECASE)
    # 如果提取的名称为空，使用默认值
    return name or "downloaded_skill"


def _is_archive(url: str, content_type: str) -> bool:
    """判断是否为压缩包"""
    # 定义压缩包的扩展名列表
    archive_extensions = (".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar")
    # 定义压缩包的 MIME 类型列表
    archive_types = (
        "application/zip",
        "application/x-zip-compressed",
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/x-bzip2",
        "application/octet-stream",
    )

    # 如果 URL 以压缩包扩展名结尾，判定为压缩包
    if any(url.lower().endswith(ext) for ext in archive_extensions):
        return True
    # 如果 content-type 匹配压缩包类型
    if any(t in content_type for t in archive_types):
        # 但是要排除 .md 或 .txt 单文件的情况（避免误判）
        if ".md" in url.lower() or ".txt" in url.lower():
            return False
        return True
    return False


# ⚠️ 以下 4 个函数（_install_from_archive / _extract_all_files / _write_member / _install_single_file）
# 已在"清理死代码"提交中移除——它们是绕过沙箱验证的旧实现，直接从压缩包解压到宿主机，
# 未被任何代码调用。现在 Skill 安装统一走 install_skill 的沙箱验证流程。


def _install_dependencies(skill_dir: Path):
    """安装 Skill 的 Python 依赖（优先在沙箱内安装，不回退到宿主机）"""
    # 检查 requirements.txt 是否存在
    req_file = skill_dir / "requirements.txt"
    if not req_file.exists():
        return

    # 尝试在沙箱内安装依赖
    try:
        from ..backends.sandbox_holder import get_sandbox
        sandbox = get_sandbox()
        if sandbox is not None:
            # 读取 requirements.txt 内容
            req_content = req_file.read_text(encoding="utf-8")
            # 将内容写入沙箱临时文件
            sandbox_req = f"/skills/requirements_{skill_dir.name}.txt"
            sandbox.write_file(sandbox_req, req_content)
            # 在沙箱中执行 pip install
            result = sandbox.execute(f"pip install -r {sandbox_req} -q", timeout=120)
            # 清理沙箱临时文件
            sandbox.execute(f"rm -f {sandbox_req}")
            if result.exit_code == 0:
                agent_logger.info(f"Skill dependencies installed in sandbox from {req_file}")
            else:
                agent_logger.warning(f"Sandbox dependency install failed: {result.output[:200]}")
            return
    except Exception as e:
        agent_logger.warning(f"Sandbox dependency install error: {e}")

    # 如果沙箱不可用，仅记录警告，不在宿主机安装依赖
    # 这样做是为了保持宿主机环境清洁，依赖会在沙箱准备好时安装
    agent_logger.warning(
        f"Sandbox unavailable, skipping dependency installation for {req_file}. "
        "Dependencies will be installed when sandbox is ready."
    )
```
---

### 4.5 `src/agent/tools/hitl_tools.py` — HITL 人工介入（138行）

**作用**：当订单必填字段缺失时，使用 LangGraph 的 `interrupt()` 暂停执行，等待用户补充信息。

```python
"""
HITL 人工介入工具
request_order_info - 当订单必填字段缺失时，向用户请求补充信息
"""
import json, re
from langchain_core.tools import tool
from langgraph.types import interrupt  # ⚡ LangGraph 的中断原语
from ..log_utils import agent_logger

# 订单必填字段
# 定义订单必填字段列表
# 这些字段在创建或更新订单时必须提供，否则数据不完整
# orderNumber: 订单编号（唯一标识）
# orderDetail: 订单明细列表（包含具体商品信息）
ORDER_REQUIRED_FIELDS = ["orderNumber", "orderDetail"]

# 定义订单明细必填字段列表
# 每个订单明细项必须包含以下三个字段
# partId: 商品/零件ID（标识具体商品）
# quantity: 订购数量（必须是正数）
# unitPrice: 商品单价（必须是正数）
ORDER_DETAIL_REQUIRED_FIELDS = ["partId", "quantity", "unitPrice"]


def validate_order_data(data: dict) -> list:
    """校验订单数据，返回缺失字段列表"""
    missing = []
    for field in ORDER_REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            missing.append(field)
    if "orderDetail" in data and data["orderDetail"]:
        for i, detail in enumerate(data["orderDetail"]):
            for field in ORDER_DETAIL_REQUIRED_FIELDS:
                if field not in detail or detail[field] is None:
                    missing.append(f"orderDetail[{i}].{field}")
    elif "orderDetail" not in missing:
        missing.append("orderDetail (至少需要一条明细)")
    return missing

def parse_supplement_text(text: str, current_data: dict) -> dict:
    """解析用户补充的自由文本，提取结构化数据
    
    支持两种格式：
    1. JSON 格式：直接解析合并
    2. 自由文本：用正则提取关键字段
       例如 "零件ID=5 数量100 单价25.5" → {"orderDetail": [{"partId": 5, ...}]}
    """
    
    # ============ 第1步：复制当前数据（避免修改原始数据） ============
    # 将 current_data 复制一份，作为返回结果的基础
    # 这样既保留了已有数据，又不会影响外部传入的字典
    result = dict(current_data)
    
    # ============ 第2步：尝试 JSON 格式解析 ============
    # 先尝试把输入文本当作 JSON 字符串解析
    # 因为用户可能直接粘贴 JSON 格式的数据
    try:
        # 将 JSON 字符串解析为 Python 字典
        # 例如: '{"orderNumber": "ORD001", "quantity": 100}' → {"orderNumber": "ORD001", "quantity": 100}
        parsed = json.loads(text)
        
        # 检查解析结果是否为字典类型
        # 只有字典才能和当前数据合并
        if isinstance(parsed, dict):
            # 将解析出的数据更新到结果中
            # 如果字段已存在则覆盖，不存在则新增
            # 例如: result 有 "orderNumber"，parsed 有 "quantity" → 两者合并
            result.update(parsed)
            # JSON 解析成功，直接返回合并后的结果
            return result
            
    # 捕获 JSON 解析错误（非 JSON 格式或格式错误）
    except (json.JSONDecodeError, TypeError):
        # 解析失败则继续往下执行，尝试自由文本解析
        pass
    
    # ============ 第3步：自由文本正则解析 ============
    # 如果 JSON 解析失败，尝试从自然语言中提取关键信息
    
    # ----- 3.1 提取 partId（物料/零件 ID） -----
    # 正则表达式: r'(?:partId|物料\s*ID|零件\s*ID)[=:\s]*(\d+)'
    # 解释:
    #   (?:partId|物料\s*ID|零件\s*ID)  - 匹配关键词（不捕获分组）
    #     - partId: 英文字段名
    #     - 物料\s*ID: 中文"物料ID"或"物料 ID"
    #     - 零件\s*ID: 中文"零件ID"或"零件 ID"
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格（0个或多个）
    #   (\d+)    - 捕获组：匹配1个或多个数字（零件ID的值）
    # 
    # 匹配示例:
    #   "partId=123"      → 匹配 "123"
    #   "物料ID: 456"     → 匹配 "456"
    #   "零件 ID 789"     → 匹配 "789"
    part_id_match = re.search(r'(?:partId|物料\s*ID|零件\s*ID)[=:\s]*(\d+)', text, re.IGNORECASE)
    
    if part_id_match:
        # 如果匹配到 partId，将其添加到订单明细中
        # result.setdefault("orderDetail", [{}]) 的含义:
        #   - 如果 result 中有 "orderDetail" 字段，获取它的值
        #   - 如果没有，设置默认值为 [{}]（一个包含空字典的列表）
        # [0] 取列表中的第一个元素（第一个订单明细项）
        # ["partId"] = int(...) 设置 partId 字段，并转为整数
        # 
        # 这样做的目的是：如果 orderDetail 还不存在，自动创建它
        result.setdefault("orderDetail", [{}])[0]["partId"] = int(part_id_match.group(1))
    
    # ----- 3.2 提取 quantity（数量） -----
    # 正则表达式: r'(?:quantity|数量)[=:\s]*(\d+)'
    # 解释:
    #   (?:quantity|数量)  - 匹配关键词（不捕获分组）
    #     - quantity: 英文字段名
    #     - 数量: 中文字段名
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格
    #   (\d+)    - 捕获组：匹配1个或多个数字（数量的值）
    #
    # 匹配示例:
    #   "quantity=100"    → 匹配 "100"
    #   "数量: 200"       → 匹配 "200"
    qty_match = re.search(r'(?:quantity|数量)[=:\s]*(\d+)', text, re.IGNORECASE)
    
    if qty_match:
        # 将提取的数量添加到订单明细的第一项
        # 同样，如果 orderDetail 不存在则自动创建
        result.setdefault("orderDetail", [{}])[0]["quantity"] = int(qty_match.group(1))
    
    # ----- 3.3 提取 unitPrice（单价） -----
    # 正则表达式: r'(?:unitPrice|单价)[=:\s]*([\d.]+)'
    # 解释:
    #   (?:unitPrice|单价)  - 匹配关键词（不捕获分组）
    #     - unitPrice: 英文字段名
    #     - 单价: 中文字段名
    #   [=:\s]*  - 匹配分隔符：等号、冒号或空格
    #   ([\d.]+) - 捕获组：匹配数字和点号（支持小数）
    #     - \d 匹配数字
    #     - \. 匹配小数点
    #     - 例如: "25.5"、"100"、"99.99"
    #
    # 匹配示例:
    #   "unitPrice=25.5"  → 匹配 "25.5"
    #   "单价: 100"       → 匹配 "100"
    #   "单价 99.99"      → 匹配 "99.99"
    price_match = re.search(r'(?:unitPrice|单价)[=:\s]*([\d.]+)', text, re.IGNORECASE)
    
    if price_match:
        # 将提取的单价添加到订单明细的第一项，转为浮点数
        result.setdefault("orderDetail", [{}])[0]["unitPrice"] = float(price_match.group(1))
    
    # ============ 第4步：返回处理后的结果 ============
    # 将合并了提取数据的字典返回给调用者
    return result


@tool
def request_order_info(extracted_data: str, missing_fields: str) -> str:
    """当订单必填字段缺失时，向用户请求补充信息。此工具会暂停执行等待用户输入。

    Args:
        extracted_data: 当前已提取的订单数据JSON字符串
        missing_fields: 缺失字段列表JSON字符串
    Returns:
        完整的订单数据JSON（所有必填字段已填充）
    """
    data = json.loads(extracted_data) if isinstance(extracted_data, str) else {}
    missing = json.loads(missing_fields) if isinstance(missing_fields, str) else []

    # 循环：校验 → 中断等待补充 → 解析 → 校验 ... 直到完整
    max_rounds = 5
    for round_num in range(max_rounds):
        if not missing:
            return json.dumps(data, ensure_ascii=False, indent=2)

        # ⚡ 核心：interrupt() 暂停执行，等待用户补充
        # 前端会收到 SSE interrupt 事件，展示输入框让用户填写
        # 用户提交后，LangGraph 恢复执行，supplement 变量就是用户输入的内容
        supplement = interrupt({
            "type": "order_info_request",
            "missing_fields": missing,
            "current_data": data,
            "message": f"请补充以下订单信息: {', '.join(missing)}",
        })

        # 解析用户补充内容
        supplement_text = ""
        if isinstance(supplement, dict):
            supplement_text = supplement.get("supplement", "")
        elif isinstance(supplement, str):
            supplement_text = supplement

        data = parse_supplement_text(supplement_text, data)  # 合并数据
        missing = validate_order_data(data)                   # 重新校验

    if missing:
        return json.dumps({"error": f"经过{max_rounds}轮补充仍有字段缺失: {missing}"})
    return json.dumps(data, ensure_ascii=False, indent=2)
```

**HITL 工作流程核心**：`interrupt()` 是 LangGraph 提供的原语，调用后 Agent 图会暂停执行，前端收到 SSE `interrupt` 事件，展示输入框让用户填写，用户提交后通过 `Command(resume=...)` 恢复执行。

---

### 4.6 `src/agent/tools/assign_skill.py` — 技能分配（69行）

**作用**：将技能分配给指定 Agent（主Agent或子Agent）。

```python
"""技能分配工具"""
import shutil
from pathlib import Path
from langchain_core.tools import tool
from ..log_utils import agent_logger

SKILLS_BASE_DIR = Path(__file__).parent.parent.parent / "skills"

@tool
def assign_skill(skill_name: str, agent_name: str = "main") -> str:
    """将技能分配给指定的 Agent。
    Args:
        skill_name: 技能名称（目录名）
        agent_name: 目标Agent名称，"main" 表示主Agent
    """
    # 在 skills 目录中查找技能
    skill_path = None
    for scope_dir in SKILLS_BASE_DIR.iterdir():
        if scope_dir.is_dir():
            candidate = scope_dir / skill_name
            if candidate.exists() and (candidate / "SKILL.md").exists():
                skill_path = candidate
                break
    if skill_path is None:
        return f"技能 '{skill_name}' 未找到"

  # ============ 判断是否为子 Agent ============
# agent_name: Agent 名称（"main" 表示主 Agent，其他名称表示子 Agent）
# 如果 agent_name != "main"，说明是要将技能分配给特定的子 Agent
if agent_name != "main":
    # ============ 构建目标路径 ============
    # SKILLS_BASE_DIR: 技能库根目录（例如: /app/skills/）
    # agent_name: 子 Agent 名称（例如: "sales_agent", "tech_support_agent"）
    # skill_name: 技能名称（例如: "order_processor", "data_analyzer"）
    # 
    # target_dir = SKILLS_BASE_DIR / agent_name / skill_name
    # 例如: /app/skills/sales_agent/order_processor/
    target_dir = SKILLS_BASE_DIR / agent_name / skill_name
    
    # ============ 检查目标目录是否已存在 ============
    # 如果不存在，才进行复制操作（避免重复复制）
    if not target_dir.exists():
        # ============ 创建父目录 ============
        # target_dir.parent 是 /app/skills/sales_agent/
        # parents=True: 如果 /app/skills/ 不存在，也会一起创建
        # exist_ok=True: 如果目录已存在，不报错
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # ============ 复制技能文件或目录 ============
        # skill_path: 技能源路径（可能是文件或目录）
        if skill_path.is_dir():
            # ---------- 复制整个目录 ----------
            # 如果 skill_path 是目录（例如: /app/skills/main/order_processor/）
            # 复制整个目录及其所有子文件到 target_dir
            # 例如: 复制 /app/skills/main/order_processor/ 
            #      到 /app/skills/sales_agent/order_processor/
            shutil.copytree(skill_path, target_dir)
        else:
            # ---------- 复制单个文件 ----------
            # 如果 skill_path 是文件（例如: /app/skills/main/order_processor.py）
            # 复制该文件到目标目录，保留原文件名
            # skill_path.name 获取文件名（例如: order_processor.py）
            # target_dir / skill_path.name 组成完整目标路径
            # 例如: 复制 /app/skills/main/order_processor.py 
            #      到 /app/skills/sales_agent/order_processor.py
            shutil.copy2(skill_path, target_dir / skill_path.name)
        
        # ============ 返回成功信息 ============
        return f"技能 '{skill_name}' 已成功分配给 Agent '{agent_name}'"
    
    # 如果目标目录已存在，直接返回（但不进行复制）
    return f"技能 '{skill_name}' 已存在于 Agent '{agent_name}' 中"

# ============ 主 Agent 的情况 ============
# 如果 agent_name == "main"，技能已在主 Agent 的技能库中
return f"技能 '{skill_name}' 已在主 Agent 技能库中可用"
```

---

### 4.7 `src/agent/tools/download_sandbox_file.py` — 沙箱文件下载（181行）

**作用**：从 Docker 沙箱容器中下载文件到宿主机 `src/download/` 目录，供用户通过 HTTP 访问。

```python
"""沙箱文件下载工具（Harness — 真实 Docker 文件提取）"""

@tool
def download_sandbox_file(remote_path: str, filename: str = "") -> str:
    """从沙箱容器中下载文件到宿主机，生成 HTTP 下载链接。

    工作原理：
    - 通过 Docker SDK 连接到沙箱容器
    - 读取容器内文件（base64 编码支持二进制）
    - 保存到宿主机 download 目录
    """
    # 方式1：从 Docker 沙箱读取
    container, client = _get_docker_container()
    if container is not None:
        read_result = container.exec_run(f"base64 '{remote_path}'")
        content = base64.b64decode(stdout.strip())
        target = DOWNLOAD_DIR / filename
        target.write_bytes(content)
        return f"✅ 文件已从沙箱下载! 下载链接: {download_url}"

    # 方式2：回退到本地文件（开发模式）
    source = Path(remote_path)
    if source.exists():
        shutil.copy2(source, target)
        return f"✅ 文件已下载!（沙箱不可用，使用本地文件）"
```


### 4.8 `src/agent/tools/document_generator.py` — 文档生成（341行，沙箱内输出）

**作用**：生成结构化文档文件（Markdown/HTML/CSV/JSON/纯文本），**优先写入沙箱** `/workspace/output/`。

**核心设计（Harness 思想）**：
- 所有文件必须先生成在 Docker 沙箱内（`/workspace/output/`）
- 用户需要下载时，通过 `download_sandbox_file` 工具从沙箱提取到本地
- 沙箱不可用时回退到本地生成

```python
def _write_to_sandbox_or_local(filename, content, title, format_name):
    """核心写入逻辑：优先写入沙箱，回退到本地"""
    sandbox = get_sandbox()

    if sandbox is not None:
        # ✅ 写入沙箱 /workspace/output/ 目录
        sandbox_path = f"/workspace/output/{filename}"
        sandbox.execute(f"mkdir -p /workspace/output")
        sandbox.write_file(sandbox_path, content)
        return f"✅ 文档已在沙箱中生成! 沙箱路径: {sandbox_path}"

    # 回退：写入本地
    file_path = LOCAL_DOWNLOAD_DIR / filename
    file_path.write_text(content, encoding="utf-8")
    return f"✅ 文档生成成功! 下载链接: {download_url}"
```

---

## 第5章 — 沙箱后端

> Agent 在执行代码时需要一个隔离的环境。沙箱后端通过 Docker 容器提供这个隔离环境，确保代码执行不会影响宿主机。
> 当前实现包含 **7 层安全防护**（只读文件系统 + tmpfs + 资源限制 + 网络隔离 + Capability 移除 + seccomp + PID 限制）和 **五态生命周期管理**。

### 5.0 `src/agent/backends/sandbox_holder.py` — 全局沙箱持有器（37行）

**作用**：全局单例，让所有自定义工具（`chart_generator`/`document_generator`/`web_fetch` 等）能访问当前活跃的沙箱实例。

```python
"""
沙箱全局持有器

让所有工具能够访问当前活跃的沙箱实例，
确保文件生成在沙箱中执行。
"""
from typing import Optional

_active_sandbox = None

def set_sandbox(sandbox):
    """设置当前活跃的沙箱实例（main_agent.py 在 Agent 创建时调用）"""
    global _active_sandbox
    _active_sandbox = sandbox

def get_sandbox():
    """获取当前活跃的沙箱实例（工具通过此函数访问沙箱）"""
    return _active_sandbox

def has_sandbox() -> bool:
    """检查沙箱是否可用"""
    if _active_sandbox is None:
        return False
    return _active_sandbox.ping()
```

**设计动机**：自定义 `@tool` 函数不像 `Backend` 那样能通过 middleware 注入上下文，需要一个全局可访问的注册中心。
- `main_agent.py` 在创建 Agent 时调用 `set_sandbox()`
- `chart_generator`/`document_generator` 等工具调用 `get_sandbox()` 获取沙箱

### 5.1 `src/agent/backends/custom_opensandbox.py` — Docker SDK 封装（415行）

**作用**：继承 deepagents 的 `BaseSandbox`，通过 Docker SDK 在隔离容器中执行命令和操作文件。包含 30+ 个方法（文件操作/目录操作/多语言运行时/生命周期/上传下载）。

```python
"""
Docker 沙箱后端
继承 deepagents BaseSandbox，通过 Docker SDK 在隔离容器中执行命令和操作文件。
容器名: erp-sandbox（由 SandboxManager 管理）.
"""
import docker
import base64
import io
import tarfile
from typing import Optional
from deepagents.backends.sandbox import (
    BaseSandbox, ExecuteResponse,
    FileDownloadResponse, FileUploadResponse,
)
from ..log_utils import sandbox_logger
from ..config import SANDBOX_WORK_DIR


class CustomOpenSandbox(BaseSandbox):
    """
    Docker 容器沙箱后端

    核心设计：
    - 继承 BaseSandbox 后，ls/read/write/edit/glob/grep 等文件操作
      自动委托给 execute()（即 docker exec）
    - 完整实现 30+ 方法：文件操作 / 目录操作 / 多语言运行时 / 生命周期
    """

    def __init__(self, container_name: str = "erp-sandbox",
                 work_dir: str = SANDBOX_WORK_DIR, timeout: int = 120):
        self._container_name = container_name
        self._work_dir = work_dir
        self._default_timeout = timeout
        self._client: Optional[docker.DockerClient] = None
        self._container = None
        self._connect()

    # === 核心执行 ===
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse: ...

    # === 文件操作（真实实现，通过 docker exec / tar 流）===
    def read_file(self, path: str) -> str: ...
    def read_file_bytes(self, path: str) -> bytes: ...      # base64 传输
    def write_file(self, path: str, content: str | bytes) -> str: ...  # 自动创建父目录
    def list_dir(self, path: str = ".") -> list[str]: ...
    def file_exists(self, path: str) -> bool: ...
    def is_directory(self, path: str) -> bool: ...
    def edit_file(self, path: str, old_text: str, new_text: str) -> str: ...
    def glob(self, pattern: str, base_path: str = ".") -> list[str]: ...
    def grep(self, pattern: str, path: str = ".", recursive: bool = True) -> list[str]: ...

    # === 目录操作 ===
    def mkdir(self, path: str) -> str: ...
    def rm(self, path: str) -> str: ...
    def cp(self, src: str, dst: str) -> str: ...
    def mv(self, src: str, dst: str) -> str: ...
    def cat(self, path: str) -> str: ...
    def pwd(self) -> str: ...
    def env(self) -> str: ...

    # === 多语言运行时 ===
    def pip_install(self, package: str) -> str: ...
    def python_exec(self, script: str) -> ExecuteResponse: ...
    def go_exec(self, code: str) -> ExecuteResponse: ...
    def node_exec(self, code: str) -> ExecuteResponse: ...

    # === 生命周期 ===
    def ping(self) -> bool: ...
    def destroy(self): ...              # 断开连接（不销毁容器）
    def destroy_container(self): ...    # 强制停止并删除容器

    # === 文件上传/下载（tar 流方式）===
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]: ...
    def download_file_to_host(self, remote_path: str, local_path: str) -> str: ...
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]: ...
    def upload_directory(self, local_dir: str, remote_dir: str) -> str: ...


# 向后兼容别名
DockerSandboxBackend = CustomOpenSandbox
```

**与旧版的关键区别**：
- 类名从 `DockerSandboxBackend` 改为 `CustomOpenSandbox`（保留别名兼容）
- 新增 20+ 个文件/目录操作方法（全部通过 docker exec 真实实现）
- 新增多语言运行时支持（Python/Go/Node.js）
- 新增 `download_file_to_host()`、`upload_directory()` 等传输方法
        
        这是核心方法——所有文件操作（read_file/write_file/glob/grep）
        都通过 execute() 执行 shell 命令实现
        """
        if self._container is None:
            return ExecuteResponse(output="[沙箱未连接]", exit_code=-1)
        
        try:
            exec_result = self._container.exec_run(
                cmd=["bash", "-c", f"cd {self._work_dir} && {command}"],
                demux=True,   # 分离 stdout/stderr
                workdir=self._work_dir,
            )
            exit_code = exec_result.exit_code
            stdout, stderr = exec_result.output
            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(stderr_text)
            output = "\n".join(output_parts) if output_parts else ""
            # 截断过长输出（100KB 限制）
            truncated = False
            if len(output) > 100_000:
                output = output[:100_000] + "\n... [output truncated]"
                truncated = True
            return ExecuteResponse(output=output, exit_code=exit_code, truncated=truncated)
        except Exception as e:
            return ExecuteResponse(output=f"[执行错误] {str(e)}", exit_code=-1)

    def ping(self) -> bool:
        """健康检查：容器是否仍在运行"""
        try:
            if self._container is None: return False
            self._container.reload()
            return self._container.status == "running"
        except Exception:
            return False

    def destroy(self):
        """断开连接（不销毁容器，容器由用户管理）"""
        self._container = None
        if self._client:
            self._client.close()

  def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
    """从容器中下载文件（通过 base64 编码读取）
    
    工作原理：
    1. 在容器内执行 base64 命令读取文件
    2. 将 base64 编码的内容解码为二进制数据
    3. 返回包含文件内容和元数据的响应对象
    """
    # 初始化结果列表，用于存储每个文件的下载结果
    results = []
    
    # 遍历所有需要下载的文件路径
    for path in paths:
        try:
            # ----- 第1步：在容器内执行 base64 编码命令 -----
            # 在容器中执行 `base64 '/path/to/file'` 命令
            # base64 命令会将文件内容编码为 ASCII 字符串输出
            # 例如：base64 '/app/data.txt' → "SGVsbG8gV29ybGQK"
            resp = self.execute(f"base64 '{path}'")
            
            # ----- 第2步：检查执行结果 -----
            # resp.exit_code == 0 表示命令执行成功
            # resp.output.strip() 获取去除首尾空白字符的输出内容
            if resp.exit_code == 0 and resp.output.strip():
                # 导入 base64 解码模块（已导入则在顶部）
                import base64
                
                # ----- 第3步：解码文件内容 -----
                # 将 base64 字符串解码为原始的二进制数据
                # base64.b64decode() 接收字符串参数，返回 bytes 对象
                # 例如：base64.b64decode("SGVsbG8gV29ybGQK") → b'Hello World\n'
                content = base64.b64decode(resp.output.strip())
                
                # 创建成功响应对象
                # FileDownloadResponse 包含：path(路径)、content(二进制内容)、error(错误信息)
                results.append(FileDownloadResponse(path=path, content=content, error=None))
            else:
                # 文件不存在或读取失败
                # 可能是路径错误、权限不足或文件为空
                results.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
                
        except Exception as e:
            # ----- 第4步：异常处理 -----
            # 捕获所有可能的异常（如：网络断开、编码错误、权限问题等）
            # 将异常信息保存到错误字段，不影响其他文件的下载
            results.append(FileDownloadResponse(path=path, content=None, error=str(e)))
    
    # 返回所有文件的下载结果列表
    return results

def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
    """上传文件到容器（通过 tar + put_archive）
    
    工作原理：
    1. 将每个文件打包成一个独立的 tar 归档
    2. 使用 Docker SDK 的 put_archive 方法将归档上传到容器
    3. 容器会自动解压 tar 包到指定目录
    """
    # 导入需要的模块
    import base64, io, tarfile
    
    # 初始化结果列表
    results = []
    
    # 遍历文件列表，每个元素是 (目标路径, 二进制内容) 的元组
    for path, content in files:
        try:
            # ----- 第1步：解析目标路径 -----
            # 获取文件所在的目录路径
            # path.rstrip("/") 移除末尾斜杠
            # .split("/") 按斜杠分割
            # [:-1] 取除最后一个部分（文件名）外的所有部分
            # "/".join(...) 重新组合成目录路径
            # 如果结果是空字符串，则使用 "/"（根目录）
            # 
            # 示例1：path = "/app/data/config.json"
            #   → path.rstrip("/") = "/app/data/config.json"
            #   → .split("/") = ["", "app", "data", "config.json"]
            #   → [:-1] = ["", "app", "data"]
            #   → "/".join(...) = "/app/data"
            # 
            # 示例2：path = "config.json"
            #   → 结果为 "/"
            dir_name = "/".join(path.rstrip("/").split("/")[:-1]) or "/"
            
            # 获取文件名（路径的最后一部分）
            # 示例：path = "/app/data/config.json" → "config.json"
            file_name = path.split("/")[-1]
            
            # ----- 第2步：创建 tar 归档（内存中） -----
            # io.BytesIO() 创建内存中的字节流缓冲区
            tar_stream = io.BytesIO()
            
            # 以写模式打开 tar 文件对象
            # fileobj=tar_stream 表示写入到内存流，而非磁盘文件
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                # 创建 tar 文件的元数据信息
                # TarInfo 包含文件名、权限、大小、修改时间等
                info = tarfile.TarInfo(name=file_name)
                
                # 设置文件大小（必须与后续内容匹配）
                info.size = len(content)
                
                # 将文件添加到 tar 包中
                # 参数1：文件元数据信息
                # 参数2：文件内容的二进制流对象
                # io.BytesIO(content) 将 bytes 包装成文件对象
                tar.addfile(info, io.BytesIO(content))
            # 退出 with 块时 tar 文件对象已关闭，但 tar_stream 仍有效
            
            # ----- 第3步：准备上传数据 -----
            # 将内存流的指针移到开头（否则读不到数据）
            tar_stream.seek(0)
            
            # ----- 第4步：上传 tar 包到容器 -----
            # self._container 是 Docker SDK 的 Container 对象
            # put_archive(目标目录, tar数据) 方法：
            #   - 将 tar 数据上传到容器的指定目录
            #   - 容器会自动解压 tar 包到该目录
            # 
            # 示例：dir_name="/app/data"，tar包内包含 "config.json"
            #   → 上传后容器内生成 /app/data/config.json
            self._container.put_archive(dir_name, tar_stream.read())
            
            # ----- 第5步：记录成功结果 -----
            results.append(FileUploadResponse(path=path, error=None))
            
        except Exception as e:
            # ----- 第6步：异常处理 -----
            # 捕获所有可能的异常（如：目录不存在、权限不足、磁盘空间满等）
            results.append(FileUploadResponse(path=path, error=str(e)))
    
    # 返回所有文件的上传结果
    return results
```

---

### 5.2 `src/agent/backends/sandbox_setup.py` — 安全沙箱创建 + 多语言运行时（413行）

**作用**：创建带有 7 层安全防护的 Docker 沙箱，初始化多语言运行时，并将项目文件完整同步到沙箱中实现真正隔离测试。

​```python
"""
沙箱创建 + 安全防护 + 多语言运行时初始化

Harness 核心思想：
1. 文件系统只读 (--read-only) + tmpfs 可写区域
2. 内存/CPU 资源限制
3. 网络隔离 (--network none 或受限网络)
4. Linux Capability 全部移除
5. seccomp 系统调用白名单
6. 可扩展多语言运行时（Python / Go / Node.js）
"""
from dataclasses import dataclass, field

@dataclass
class SandboxConfig:
    """沙箱创建配置（可扩展）"""
    image: str = SANDBOX_IMAGE
    name: str = "erp-sandbox"
    work_dir: str = SANDBOX_WORK_DIR
    # --- 安全防护 ---
    read_only: bool = True
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network_mode: str = "bridge"      # "none" = 完全隔离
    tmpfs_size: str = "128m"
    drop_all_caps: bool = True
    use_seccomp: bool = True
    # --- 多语言运行时 ---
    runtimes: list[str] = field(default_factory=lambda: ["python"])
    env_vars: dict[str, str] = field(default_factory=dict)


def create_secure_sandbox(config: SandboxConfig) -> CustomOpenSandbox:
    """创建带 7 层安全防护的沙箱容器"""
    # 1. --read-only          文件系统只读
    # 2. --tmpfs /tmp         临时目录内存挂载
    # 3. --memory="512m"      内存上限
    # 4. --cpus="1.0"         CPU 上限
    # 5. --network bridge     网络隔离/受限
    # 6. --cap-drop ALL       移除所有 Linux Capability
    # 7. --security-opt       seccomp 系统调用白名单
    ...

def _init_runtimes(sandbox, config):
    """初始化多语言运行时（Python/Go/Node.js）"""
    ...

def _sync_project_files(sandbox, config):
    """将项目文件完整同步到沙箱（实现真正隔离测试）"""
    # 同步 skills/ 目录到 /skills
    # 同步 src/ 目录到 /workspace/src
    ...

def create_and_setup_sandbox(user_id: str = "default") -> CustomOpenSandbox:
    """创建沙箱 + 安全防护 + 运行时初始化 + 文件同步"""
    config = SandboxConfig(name=f"erp-sandbox-{user_id[:8]}")
    sandbox = create_secure_sandbox(config)
    _init_runtimes(sandbox, config)
    _sync_project_files(sandbox, config)
    return sandbox
```

**与旧版的关键区别**：
- 旧版只有 21 行，仅 `mkdir -p /workspace /skills /data /analysis`
- 新版 413 行，包含完整的 7 层安全防护 + 多语言运行时 + 项目文件同步
- 新增 `SandboxConfig` 数据类，支持灵活配置
- 新增 `seccomp.json` 系统调用白名单文件

---

### 5.3 `src/agent/backends/sandbox_manager.py` — 五态生命周期管理（494行）

**作用**：实现沙箱的完整五态生命周期（预热池 → 认领 → MongoDB缓存 → 新建 → 销毁），支持快速分配、故障恢复和超时回收。

```python
"""
沙箱生命周期管理（Harness 五态模型）

五态流转：
┌─────────┐    认领     ┌─────────┐    持久化    ┌────────────┐
│  预热池  │ ─────────→ │  已认领  │ ─────────→ │ MongoDB缓存 │
│ (WARM)  │             │ (CLAIMED)│             │  (CACHED)  │
└─────────┘             └─────────┘             └────────────┘
     ↑                       │
     │ 补充预热               │ 故障/超时
     │                       ↓
┌─────────┐             ┌─────────┐
│  新建    │ ←────────── │  销毁    │
│ (CREATE)│   预热池空    │(DESTROY)│
└─────────┘             └─────────┘
"""

class SandboxState:
    WARM = "warm"           # 预热池中的空闲容器
    CLAIMED = "claimed"     # 已分配给用户
    CACHED = "cached"       # 已持久化到 MongoDB
    CREATING = "creating"   # 正在创建中
    DESTROYED = "destroyed" # 已销毁

class SandboxEntry:
    """沙箱条目（跟踪容器的完整生命周期）"""
    sandbox: CustomOpenSandbox
    user_id: str
    state: str
    created_at: datetime
    last_active: datetime

class SandboxManager:
    """沙箱生命周期管理器（单例）
    
    核心职责：
    - 预热池管理（保持 N 个空闲容器，认领时 < 100ms）
    - user_id → sandbox 映射（每个用户一个独立沙箱）
    - MongoDB 持久化 user→container 映射（服务重启不丢失）
    - 健康检查 + 自动重建故障容器
    - 超时回收闲置沙箱（默认 30 分钟）
    """
    def get_sandbox(self, user_id: str) -> CustomOpenSandbox: ...
    def claim_from_pool(self, user_id: str) -> CustomOpenSandbox: ...
    def rebuild(self, user_id: str) -> CustomOpenSandbox: ...
    def destroy_user_sandbox(self, user_id: str): ...
    def health_check_all(self): ...
    def _reclaim_idle(self): ...
    def _persist_binding(self, user_id: str, container_id: str): ...
    def _restore_bindings(self): ...

sandbox_manager = SandboxManager()
```

**与旧版的关键区别**：
- 旧版 83 行，只有基本的 get/rebuild/destroy 三个方法
- 新版 494 行，完整实现五态生命周期
- 新增预热池（warm pool）机制，认领时 < 100ms
- 新增 MongoDB 持久化 user→container 映射
- 新增健康检查 + 自动重建 + 超时回收

```python
"""
沙箱生命周期管理
五态：预热池 → 认领 → MongoDB缓存 → 新建 → 销毁
"""
# 导入类型注解，用于声明字典的值类型
from typing import Dict, Optional
# 导入自定义沙箱类（这里存在导入问题，稍后说明）
from .custom_opensandbox import CustomOpenSandbox
# 导入沙箱创建和初始化函数
from .sandbox_setup import create_and_setup_sandbox
# 导入日志工具
from ..log_utils import sandbox_logger


class SandboxManager:
    """沙箱生命周期管理器（单例）
    
    核心职责：
    - user_id → sandbox 映射（每个用户一个独立沙箱）
    - 沙箱不可达时自动重建
    """
    
    # ============ 单例模式实现 ============
    # _instance 是类变量（属于类本身，不属于实例）
    # 用于存储唯一的实例对象，初始为 None
    # 所有通过 SandboxManager() 创建的对象共享这个变量
    _instance = None
    
    def __new__(cls):
        """__new__ 是 Python 创建实例的第一步（在 __init__ 之前调用）
        
        单例模式的核心逻辑：
        1. 检查类变量 _instance 是否已经存在实例
        2. 如果不存在，调用父类的 __new__ 创建新实例并保存到 _instance
        3. 如果已存在，直接返回保存的实例
        4. 这样无论调用多少次 SandboxManager()，都返回同一个对象
        
        cls._instance 的作用：
        - 存储唯一的实例对象
        - 是类级别的变量，所有实例共享
        - 用于判断是否已经创建过实例
        """
        if cls._instance is None:
            # 第一次调用：调用父类 object.__new__ 创建实例
            # super().__new__(cls) 会分配内存并创建对象
            cls._instance = super().__new__(cls)
            # 为新实例添加 _initialized 标记，表示还未初始化
            cls._instance._initialized = False
        # 后续调用：直接返回已保存的实例
        return cls._instance

    def __init__(self):
        """__init__ 在 __new__ 之后调用，用于初始化实例属性
        
        由于单例模式，__init__ 可能会被调用多次（每次调用 SandboxManager() 时）
        但通过 _initialized 标记，确保只初始化一次
        """
        # 检查是否已经初始化过
        if self._initialized:
            # 已初始化则直接返回，避免重复初始化
            return
        
        # 标记为已初始化，防止后续重复执行
        self._initialized = True
        
        # _user_sandboxes: 存储用户ID到沙箱实例的映射
        # 格式：{"user123": CustomOpenSandbox实例, "user456": CustomOpenSandbox实例}
        # 每个用户拥有独立的沙箱，互不干扰
        self._user_sandboxes: Dict[str, CustomOpenSandbox] = {}
        
        # _warm_pool: 预热池，存储预先创建好的沙箱实例（五态中的"预热池"）
        # 预留扩展：可以预先创建沙箱，加快获取速度
        self._warm_pool: list = []

    def get_sandbox(self, user_id: str) -> CustomOpenSandbox:
        """获取用户的沙箱实例（不存在则创建）
        
        工作流程：
        1. 检查用户是否已有沙箱
        2. 如果有，检查沙箱是否健康
        3. 如果健康，直接返回
        4. 如果不健康，删除旧实例，重新创建
        5. 如果没有，创建新的沙箱
        """
        # 检查用户是否已经有沙箱实例
        if user_id in self._user_sandboxes:
            # 从字典中获取该用户的沙箱
            sandbox = self._user_sandboxes[user_id]
            
            # ping() 方法检查沙箱是否健康（容器是否在运行）
            if sandbox.ping():
                # 沙箱健康，直接返回
                return sandbox
            else:
                # 沙箱不健康（容器意外停止了），记录警告日志
                sandbox_logger.warning(f"Sandbox unhealthy for user {user_id}, rebuilding...")
                # 从字典中删除不健康的沙箱实例
                # 释放内存，等待垃圾回收
                del self._user_sandboxes[user_id]
        
        # 执行到这里，说明用户没有沙箱或沙箱不健康
        # 调用创建函数新建沙箱（包含环境初始化）
        sandbox = create_and_setup_sandbox(user_id)
        
        # 将新建的沙箱存入字典，以便下次快速获取
        self._user_sandboxes[user_id] = sandbox
        
        # 返回新建的沙箱
        return sandbox

    def rebuild(self, user_id: str = "default_user") -> CustomOpenSandbox:
        """重建用户沙箱
        
        使用场景：
        - 用户报告沙箱异常
        - 需要清空沙箱数据
        - 切换用户环境
        """
        # 检查用户是否有沙箱
        if user_id in self._user_sandboxes:
            try:
                # 尝试销毁旧沙箱（释放容器连接等资源）
                # destroy() 方法会关闭连接，但不销毁Docker容器
                self._user_sandboxes[user_id].destroy()
            except Exception:
                # 销毁过程出现异常（如容器已不存在），忽略错误继续
                pass
            # 从字典中删除旧沙箱引用
            del self._user_sandboxes[user_id]
        
        # 调用 get_sandbox 创建新的沙箱（会自动调用 create_and_setup_sandbox）
        return self.get_sandbox(user_id)

    def destroy_user_sandbox(self, user_id: str):
        """销毁指定用户的沙箱
        
        使用场景：
        - 用户退出登录
        - 清理空闲沙箱
        - 节省资源
        """
        # 检查用户是否有沙箱
        if user_id in self._user_sandboxes:
            # 调用沙箱的 destroy 方法释放资源
            self._user_sandboxes[user_id].destroy()
            # 从字典中删除引用
            del self._user_sandboxes[user_id]


# ============ 创建全局单例实例 ============
# 模块加载时立即创建 SandboxManager 实例
# 由于单例模式，无论在哪里导入 sandbox_manager，都是同一个对象
# 所有模块共享同一个沙箱管理器，保证一致性
sandbox_manager = SandboxManager()
```

---

### 5.4 `src/agent/backends/sandbox_proxy.py` — 代理层+热替换（18个委托方法全部实现）

**作用**：提供稳定的沙箱接口句柄，支持运行时热替换底层沙箱实例。18 个委托方法全部真实实现（而非空壳函数），这是熔断器模式的基础——当沙箱崩溃时，只需 `replace_backend()` 即可无缝切换。

```python
"""
沙箱代理层（热替换，18个方法显式委托）
SandboxBackendProxy - 稳定句柄层，支持运行时热替换底层沙箱实例
"""
from typing import Optional
from .custom_opensandbox import CustomOpenSandbox
from ..log_utils import sandbox_logger

class SandboxBackendProxy:
    """沙箱代理器 - 18个方法显式委托 + replace_backend() 热替换"""

    def __init__(self, backend: Optional[CustomOpenSandbox] = None):
        self._backend = backend

    def replace_backend(self, new_backend: CustomOpenSandbox):
        """热替换底层沙箱实例（沙箱重建后调用）"""
        old = self._backend
        self._backend = new_backend
        if old: old.destroy()
        sandbox_logger.info("Sandbox backend hot-swapped")

    @property
    def backend(self) -> CustomOpenSandbox:
        if self._backend is None:
            raise RuntimeError("No sandbox backend available")
        return self._backend

    # === 18个显式委托方法 ===
    def execute(self, command: str, timeout: int = 30) -> dict:
        return self.backend.execute(command, timeout)
    def read_file(self, path: str) -> str:
        return self.backend.read_file(path)
    def write_file(self, path: str, content: str) -> str:
        return self.backend.write_file(path, content)
    def list_dir(self, path: str = ".") -> list:
        return self.backend.list_dir(path)
    def ping(self) -> bool:
        if self._backend is None: return False
        return self._backend.ping()
    def destroy(self):
        if self._backend: self._backend.destroy()
    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        content = self.backend.read_file(path)
        if old_text in content:
            content = content.replace(old_text, new_text, 1)
            return self.backend.write_file(path, content)
        return f"Text not found in {path}"
    def glob(self, pattern: str) -> list:
        import fnmatch
        all_files = self.backend.list_dir(".")
        return [f for f in all_files if fnmatch.fnmatch(f, pattern)]
    def grep(self, pattern: str, path: str = ".") -> list:
        import re
        results = []
        content = self.backend.read_file(path)
        for i, line in enumerate(content.split("\n"), 1):
            if re.search(pattern, line):
                results.append(f"{i}: {line}")
        return results
    def mkdir(self, path: str) -> str:
        return self.backend.execute(f"mkdir -p {path}")["stdout"]
    def rm(self, path: str) -> str:
        return self.backend.execute(f"rm -rf {path}")["stdout"]
    def cp(self, src: str, dst: str) -> str:
        return self.backend.execute(f"cp -r {src} {dst}")["stdout"]
    def mv(self, src: str, dst: str) -> str:
        return self.backend.execute(f"mv {src} {dst}")["stdout"]
    def cat(self, path: str) -> str:
        return self.backend.read_file(path)
    def pwd(self) -> str:
        return self.backend.execute("pwd")["stdout"].strip()
    def env(self) -> str:
        return self.backend.execute("env")["stdout"]
    def pip_install(self, package: str) -> str:
        return self.backend.execute(f"pip install {package} -q")["stdout"]
    def python_exec(self, script: str) -> dict:
        self.backend.write_file("/tmp/_script.py", script)
        return self.backend.execute("python /tmp/_script.py")
```

**设计决策**：为什么需要 Proxy 层？
- 沙箱可能崩溃重建，但 Agent 持有的 backend 引用不能变
- Proxy 层提供稳定句柄，内部可通过 `replace_backend()` 热替换
- 类似设计模式：代理模式 + 策略模式

---

## 第6章 — 中间件栈

> 中间件是 Harness 架构的核心扩展点。7 个自定义中间件 + Harness 阶段状态机 + RubricMiddleware 评审器，按照固定顺序执行。

### 中间件执行顺序

```
before_agent 阶段（Agent 执行前，按注册顺序执行）：
  1. SandboxHealthMiddleware    → ping 沙箱，不可达则重建
  2. HarnessPhaseMiddleware     → ★识别任务类型→注入 rubric→置 phase=planning
  3. ContextInjectionMiddleware → 注入用户偏好/身份
  4. SkillsSyncMiddleware       → 同步技能文件到沙箱
  5. UserSkillsRestoreMiddleware → 恢复持久化技能
  6. ToolsSummarizationMiddleware → 检查上下文长度
  7. MemoryUpdateMiddleware     → 提取并持久化用户偏好
  8. SandboxCircuitBreakerMiddleware → 熔断器保护

after_model 阶段（每次模型调用后）：
  HarnessPhaseMiddleware → 模型返回工具调用时置 phase=executing

after_agent 阶段（Agent 执行后，按逆序执行）：
  RubricMiddleware     → ★grader 子Agent 对照 rubric 打分，needs_revision 打回重做
  HarnessPhaseMiddleware → 构建结构化 review_result，置终态 phase

最后：ModelCallLimitMiddleware + ToolCallLimitMiddleware（框架内置）
```

> **关键设计（本次改造）**：`before_agent` 按注册顺序、`after_agent` 按逆序执行。
> 因此 `[HarnessPhaseMiddleware, RubricMiddleware]` 的注册顺序恰好保证：
> - before 阶段先注入 rubric，评审器随后据此重置评分状态
> - after 阶段评审器先打分，Harness 中间件再根据 `_rubric_status` 置终态阶段

### 6.0 `src/agent/harness.py` — Harness 阶段状态机 + rubric 注入（★新增）

**作用**：这是"真 Harness 架构"的核心模块。它将 Planning → Executing → Review → Result 四阶段从 prompt 软约束升级为 **graph state 中的结构化字段**，并把评审交给框架原生 `RubricMiddleware`。

```python
"""
Harness 编排模块（真 Harness 架构核心）
职责：
1. HarnessPhaseState — 扩展 LangGraph 状态（phase / plan / review_result）
2. load_harness_config — 加载声明式 DSL 配置（harness_config.yaml）
3. build_rubric / detect_task_type — 按任务类型生成评审标准
4. HarnessPhaseMiddleware — 阶段状态机 + rubric 注入
"""

# ============================================================
# 导入依赖
# ============================================================

# typing_extensions: 类型提示扩展库，支持 NotRequired（可选字段）
from typing_extensions import NotRequired, TypedDict

# AgentMiddleware: LangChain 的中间件基类，用于在 Agent 执行前后插入逻辑
# Runtime: 运行时上下文，包含配置和工具等信息
from langchain.agents.middleware import AgentMiddleware, Runtime

# AgentState: LangChain 定义的 Agent 状态基类
from langchain.agents.middleware.types import AgentState

# Phase: 枚举类型，定义工作流的4个阶段（planning/executing/reviewing/result）
# ReviewResult: 评审结果的数据结构（verdict/explanation/criteria/iteration）
from .schema import Phase, ReviewResult

# agent_logger: 日志记录器，用于输出调试/运行日志
from .log_utils import agent_logger

# Path: 路径处理库，用于定位配置文件
from pathlib import Path


# ============================================================
# 配置文件路径
# ============================================================

# 定义 Harness 配置文件的路径（与当前文件同目录下的 harness_config.yaml）
HARNESS_CONFIG_PATH = Path(__file__).parent / "harness_config.yaml"


# ============================================================
# 扩展状态定义
# ============================================================

class HarnessPhaseState(AgentState):
    """Harness 扩展状态：在 DeepAgentState 基础上增加阶段/计划/评审字段。

    通过 HarnessPhaseMiddleware.state_schema 声明，由框架自动合并进 graph state，
    因此这些字段会出现在 checkpoint 和 values 流中（可观测、可恢复）。
    """
    
    # phase: 当前工作流阶段，可选值为 planning/executing/reviewing/result
    # NotRequired 表示这个字段不是必须的，可以不传
    phase: NotRequired[str]
    
    # plan: 结构化任务规划，包含任务分解、步骤等
    # dict 类型，可以存储任意键值对
    plan: NotRequired[dict]
    
    # review_result: 评审结果，包含 verdict（通过/需修改）、explanation（解释）等
    review_result: NotRequired[dict]


# ============================================================
# 加载配置文件
# ============================================================

def load_harness_config(config_path=None) -> dict:
    """加载 Harness DSL 配置，缺失时回退到 _DEFAULT_CONFIG"""
    # 函数体略（实际会读取 YAML 文件并解析为 dict）
    # 如果文件不存在或读取失败，返回默认配置
    pass


# ============================================================
# 识别任务类型
# ============================================================

def detect_task_type(messages, config) -> str:
    """根据用户消息关键词识别任务类型（analysis/order/inventory/supplier/default）"""
    # messages: 对话历史，包含用户和 AI 的消息
    # config: 加载的配置字典，包含 task_types 关键词映射
    # 返回: 匹配的任务类型字符串，如果没有匹配则返回 "default"
    pass


# ============================================================
# 构建评审标准
# ============================================================

def build_rubric(task_type, config) -> str:
    """按任务类型生成评审标准字符串（交给 RubricMiddleware 打分）"""
    # task_type: 任务类型，如 "analysis"、"order" 等
    # config: 配置字典，包含 rubrics 评审标准定义
    # 返回: 对应任务类型的评审标准文本
    pass


# ============================================================
# 阶段状态机中间件（核心）
# ============================================================

class HarnessPhaseMiddleware(AgentMiddleware):
    """Harness 阶段状态机中间件。
    
    这个中间件在 Agent 执行的不同生命周期钩子中插入逻辑，
    控制工作流在4个阶段之间流转。
    """
    
    # 声明这个中间件扩展的状态结构
    # 框架会自动把 HarnessPhaseState 的字段合并到全局状态中
    state_schema = HarnessPhaseState

    # ============================================================
    # before_agent: Agent 执行前调用
    # ============================================================
    
    def before_agent(self, state, runtime):
        """识别任务类型 → 注入 rubric（激活评审器）→ 置 phase=planning"""
        
        # 准备状态更新字典
        updates = {"phase": Phase.planning.value}  # 将阶段设为 "planning"
        
        # 检查状态中是否已有 rubric（评审标准）
        if not state.get("rubric"):
            # 从消息中识别任务类型
            task_type = detect_task_type(state.get("messages", []), self._config)
            
            # 根据任务类型构建评审标准
            rubric = build_rubric(task_type, self._config)
            
            # 如果成功构建了评审标准，加入更新
            if rubric:
                updates["rubric"] = rubric
        
        # 返回更新，框架会自动合并到状态中
        return updates

    # ============================================================
    # after_model: 模型调用后调用
    # ============================================================
    
    def after_model(self, state, runtime):
        """模型返回工具调用 → 置 phase=executing（结构性写入，非正则猜测）"""
        
        # 获取当前对话消息
        messages = state.get("messages", [])
        
        # 检查最后一条消息是否包含工具调用（tool_calls）
        # 如果包含，说明 Agent 正在执行工具，进入执行阶段
        if messages and getattr(messages[-1], "tool_calls", None):
            # 将阶段切换为 "executing"
            return {"phase": Phase.executing.value}
        
        # 没有工具调用，不更新状态
        return None

    # ============================================================
    # after_agent: Agent 完整执行后调用
    # ============================================================
    
    def after_agent(self, state, runtime):
        """根据评审状态置终态 + 构建结构化 review_result 持久化到 checkpoint"""
        
        # 获取评审状态（由 RubricMiddleware 设置）
        # _rubric_status 可能的值: "passed"（通过）或 "needs_revision"（需修改）
        status = state.get("_rubric_status")
        
        # 准备状态更新字典
        updates = {}
        
        # 如果有评审状态，构建结构化的评审结果
        if status:
            # 获取所有评审评估记录（列表）
            evaluations = state.get("_rubric_evaluations") or []
            
            # 取最后一次评估结果
            last = evaluations[-1] if evaluations else {}
            
            # 构建 ReviewResult 对象并转为字典
            updates["review_result"] = ReviewResult(
                verdict=status,  # 评审结论: "passed" 或 "needs_revision"
                explanation=last.get("explanation", ""),  # 评审解释
                criteria=[dict(c) for c in last.get("criteria", [])],  # 详细标准打分
                iteration=last.get("iteration", 0),  # 当前是第几次评审
            ).model_dump()  # 转为字典以便序列化存储
        
        # 根据评审状态决定最终阶段
        # 如果需要修改 → 进入 reviewing 阶段（可能触发重新执行）
        # 如果通过 → 进入 result 阶段（任务完成）
        updates["phase"] = (
            Phase.reviewing.value if status == "needs_revision"
            else Phase.result.value
        )
        
        # 返回更新
        return updates
```

**配套 DSL 配置** `harness_config.yaml`（声明式，改流程不改代码）：

```yaml
# ============================================================
# Harness 工作流声明式配置（DSL）
# 将 Planning → Executing → Review → Result 四阶段与评审标准
# 从 prompts.py 中抽离，实现"改流程不改代码"。
# ============================================================

# ═══════════════════════════════════════════════════════════════
# 阶段定义（顺序即流转顺序，label 用于前端展示）
# ═══════════════════════════════════════════════════════════════
phases:                           # 工作流程的4个阶段
  - name: planning                # 阶段1：规划阶段
    label: "📝 规划中"            # 前端显示的友好名称
  - name: executing               # 阶段2：执行阶段
    label: "⚙️ 执行中"            # 前端显示"执行中"
  - name: reviewing               # 阶段3：审查阶段
    label: "🔍 审查中"            # 检查执行结果是否符合要求
  - name: result                  # 阶段4：结果阶段
    label: "📊 已完成"            # 任务完成，输出最终结果

# ═══════════════════════════════════════════════════════════════
# 评审器配置（由 RubricMiddleware 消费）
# ═══════════════════════════════════════════════════════════════
review:
  max_iterations: 3               # 最多评审3次，如果一直不合格就停止
  model: null                     # 使用默认AI模型；可指定如"gpt-4"

# ═══════════════════════════════════════════════════════════════
# 任务类型识别关键词（用于自动选择评审标准）
# ═══════════════════════════════════════════════════════════════
task_types:                       # 根据用户问题中的关键词自动判断任务类型
  analysis:                       # 分析类任务
    keywords: [分析, 对比, 统计, 趋势, 报表, 图表, 报告, 评估]
  order:                          # 订单类任务
    keywords: [下单, 采购, 订单, 新增, 修改, 审批, 创建]
  inventory:                      # 库存类任务
    keywords: [库存, 入库, 出库, 盘点, 预警]
  supplier:                       # 供应商类任务
    keywords: [供应商, 供货, 信用]

# ═══════════════════════════════════════════════════════════════
# 各任务类型的评审标准（"什么算完成"）
# ═══════════════════════════════════════════════════════════════
rubrics:                          # 评分标准（检查表）
  default: |                      # 默认标准（所有任务都适用）
    1. 完整回答用户的问题，未遗漏关键信息
    2. 所有数据均来自真实工具调用，未编造数据
    3. 输出使用 Markdown 格式，列表数据使用表格
    4. 金额保留两位小数，日期格式为 yyyy-MM-dd
    5. 结论有数据支撑，并给出可执行的建议

  analysis: |                     # 分析任务的专用标准
    1. 使用 MCP 工具获取了真实业务数据（供应商/零部件/库存/订单）
    2. 对数据进行了清洗、汇总，提取出关键指标
    3. 输出了包含数据表格的结构化分析报告
    4. 生成了可视化图表（图表类型与数据类型匹配）
    5. 分析结论有明确的数据支撑，采购建议可执行

  order: |                        # 订单任务的专用标准
    1. 提取了完整的订单字段（orderNumber、orderDetail、数量、单价）
    2. 缺失字段时通过 request_order_info 向用户询问，未擅自假设
    3. 数据校验通过：quantity >= 1，unitPrice > 0，partId 有效
    4. 创建/修改前向用户展示了完整订单摘要
    5. 写操作已触发人工审批中断，未绕过审批

  inventory: |                    # 库存任务的专用标准
    1. 使用库存工具获取了真实库存数据
    2. 准确识别了低于安全库存的预警项
    3. 入库/出库操作的数据（partId、数量）完整且合法
    4. 输出包含库存状态总结与补货建议

  supplier: |                     # 供应商任务的专用标准
    1. 使用供应商工具获取了真实供应商数据
    2. 准确展示了信用评级、合作状态、供货能力
    3. 对比分析有明确的数据维度
    4. 给出了供应商选择或合作建议

# ═══════════════════════════════════════════════════════════════
# 可观测性配置（监控和调试）
# ═══════════════════════════════════════════════════════════════
observability:
  trace_phase_transitions: true   # 是否记录每个阶段切换的日志
```

**设计决策**：
- 为什么阶段是 `NotRequired[str]` 而非 `Enum`？→ LangGraph state 必须可 JSON 序列化（checkpoint 持久化），存枚举的 `.value`
- 为什么 rubric 在 `before_agent` 注入而非构造时？→ rubric 需根据用户消息的任务类型动态选择
- 为什么 `after_model` 才置 executing？→ 只有模型真正产出工具调用才算进入执行阶段



### 6.1 `sandbox_health.py` — 沙箱健康检查（92行）

```python
"""中间件 1: 沙箱健康检查 + 自动恢复"""
import time
from langchain.agents.middleware import AgentMiddleware, Runtime
from ..log_utils import middleware_logger

class SandboxHealthMiddleware(AgentMiddleware):
    """
    在每次 Agent 执行前 ping 沙箱容器。
    连续 2 次不可达时触发 sandbox_manager.rebuild() 重建。
    限频检查（默认 60s 间隔），避免每次调用都 ping。
    """
    def __init__(self, sandbox_manager=None, check_interval: float = 60.0):
        self._sandbox_manager = sandbox_manager
        self._check_interval = check_interval
        self._last_check: float = 0
        self._consecutive_failures: int = 0
        self.tools = []

    def before_agent(self, state, runtime):
        now = time.time()
        if now - self._last_check < self._check_interval:
            return None  # 限频：未到检查时间
        self._last_check = now
        if self._sandbox_manager is None:
            return None  # 开发模式：始终健康
        try:
            is_alive = self._ping_sandbox()
            if is_alive:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= 2:
                    self._sandbox_manager.rebuild()  # 连续 2 次失败 → 重建
                    self._consecutive_failures = 0
        except Exception as e:
            middleware_logger.error(f"Health check error: {e}")
        return None

    def _ping_sandbox(self) -> bool:
        """通过 docker exec echo 检测容器存活"""
        container_id = self._sandbox_manager.get_active_container()
        if not container_id: return False
        import docker
        client = docker.from_env()
        container = client.containers.get(container_id)
        exit_code, _ = container.exec_run("echo ok", timeout=5)
        return exit_code == 0
```

### 6.2 `context_injection.py` — 用户上下文注入（工厂模式隔离）

**旧版问题**：中间件实例是全局单例的，所有请求共享同一个 `_user_context`，导致用户数据串扰（用户A的上下文被用户B覆盖）。

**新版解决方案**：使用工厂模式，每次请求创建新的中间件实例，确保用户数据隔离。

```python
"""
中间件 2: 用户上下文注入（工厂模式隔离）

旧版问题：全局单例 → 用户A的上下文被用户B覆盖
新版方案：工厂模式 → 每次请求创建新实例
"""
from langchain.agents.middleware import AgentMiddleware
from ..schema import ProcurementContext


class ContextInjectionMiddleware(AgentMiddleware):
    """用户上下文注入 — 每次请求创建独立实例"""

    def __init__(self, user_context: ProcurementContext | None = None):
        # 每次创建都是独立的上下文实例，不共享
        self._user_context = user_context or ProcurementContext()
        self.tools = []

    def before_agent(self, state, runtime):
        """将用户上下文注入到 state 中"""
        if isinstance(state, dict):
            state["_user_context"] = {
                "user_id": self._user_context.user_id,
                "username": self._user_context.username,
                "preferences": self._user_context.preferences,
            }
        return None

    def update_context(self, user_context: ProcurementContext):
        """动态更新用户上下文"""
        self._user_context = user_context
```

**与旧版的关键区别**：
- 旧版 `before_agent` 直接 `return None`，上下文未实际注入
- 新版将用户上下文写入 state，确保 Agent 执行时可访问
- 配合 `main_agent.py` 中的工厂函数，每次请求创建新实例

### 6.3 `skills_sync.py` — 技能增量同步（文件夹级 SHA256 哈希）

**旧版问题**：
1. 用文件名（而非相对路径）作为哈希 key，同名文件在不同子目录会互相覆盖
2. 同步时只写文件名到 `/skills/` 根目录，完全丢失子目录结构
3. 只在首次执行时同步一次，后续本地文件变更不会增量更新

**新版解决方案**：
- 哈希 key 使用相对路径（如 `procurement/web-scraper/SKILL.md`）
- 同步时保留完整子目录结构
- 每次 `before_agent` 都检查哈希变更，支持增量更新
- 哈希计算基于整个 skill 文件夹（而非单个 .md 文件）

```python
"""
中间件 3: 本地技能同步到沙箱（文件夹级 SHA256 哈希增量同步）
"""
import hashlib
from pathlib import Path
from langchain.agents.middleware import AgentMiddleware


class SkillsSyncMiddleware(AgentMiddleware):
    """每次执行时将本地 src/skills/ 同步到沙箱 /skills/（增量）"""

    def __init__(self, skills_dir=None, sandbox_backend=None):
        self._skills_dir = Path(skills_dir) if skills_dir else None
        self._sandbox_backend = sandbox_backend
        # ✅ 修复：用相对路径作为 key（而非文件名）
        self._file_hashes: dict[str, str] = {}
        self.tools = []

    def before_agent(self, state, runtime):
        """每次执行都检查并同步变更的技能文件"""
        if self._skills_dir and self._skills_dir.exists():
            if self._sandbox_backend:
                self._sync_to_sandbox()
            else:
                self._validate_local_skills()
        return None

    def _sync_to_sandbox(self):
        """增量同步：基于 SHA256 哈希比对，保留完整目录结构"""
        for file_path in self._skills_dir.rglob("*"):
            if file_path.is_file():
                # ✅ 修复：用相对路径作为 key
                rel_path = str(file_path.relative_to(self._skills_dir))
                file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

                if self._file_hashes.get(rel_path) != file_hash:
                    content = file_path.read_text(encoding="utf-8")
                    # ✅ 修复：保留子目录结构
                    # 例如：procurement/web-scraper/scraper.py
                    #    → /skills/procurement/web-scraper/scraper.py
                    remote_path = f"/skills/{rel_path}"
                    self._sandbox_backend.write_file(remote_path, content)
                    self._file_hashes[rel_path] = file_hash

        # ✅ 新增：检测远程已删除的文件并清理
        # ...
```

### 6.4 `user_skills_restore.py` — 持久化技能恢复（修复 6 个问题）

**旧版 6 个问题**：
1. `search()` 返回结果未做空值保护
2. 写入文件前未创建父目录
3. `_restored` 单例标记导致后续新持久化技能无法加载
4. 恢复失败只记录 warning（实际是功能性故障）
5. 无同名技能覆盖保护
6. 每次全量写入，无增量同步

**新版解决方案**：全部修复上述 6 个问题。

```python
"""
中间件 4: 持久化技能恢复（修复 6 个问题）
从 StoreBackend 恢复用户持久化的自定义技能到沙箱
"""
from typing import Any
from langchain.agents.middleware import AgentMiddleware
from ..log_utils import middleware_logger


class UserSkillsRestoreMiddleware(AgentMiddleware):
    def __init__(self, store=None, user_id: str = "default_user",
                 sandbox_backend=None):
        self._store = store
        self._user_id = user_id
        self._sandbox_backend = sandbox_backend
        # ✅ 修复3: 移除 _restored 单例标记，每次请求都检查
        # ✅ 修复6: 用哈希缓存实现增量同步
        self._restored_hashes: dict[str, str] = {}
        self.tools = []

    def before_agent(self, state, runtime):
        # ✅ 修复3: 每次都检查，而非只执行一次
        if self._store is not None and self._sandbox_backend is not None:
            self._restore_skills()
        return None

    def _restore_skills(self):
        try:
            namespace = ("persisted-skills", self._user_id)
            # ✅ 修复1: 空值保护
            items = self._store.search(namespace)
            if not items:
                return

            restored_count = 0
            for item in items:
                skill_name = item.key
                skill_content = item.value.get("content", "") if isinstance(item.value, dict) else ""
                skill_path = item.value.get("path", f"/skills/custom/{skill_name}") if isinstance(item.value, dict) else f"/skills/custom/{skill_name}"

                if skill_content:
                    # ✅ 修复6: 增量同步（哈希比对）
                    import hashlib
                    content_hash = hashlib.sha256(skill_content.encode()).hexdigest()
                    if self._restored_hashes.get(skill_path) == content_hash:
                        continue  # 内容未变，跳过

                    # ✅ 修复2: 创建父目录
                    parent_dir = "/".join(skill_path.rstrip("/").split("/")[:-1])
                    if parent_dir:
                        self._sandbox_backend.execute(f"mkdir -p '{parent_dir}'")

                    # ✅ 修复5: 检查同名覆盖
                    if self._sandbox_backend.file_exists(skill_path):
                        middleware_logger.info(f"Overwriting existing skill: {skill_path}")

                    self._sandbox_backend.write_file(skill_path, skill_content)
                    self._restored_hashes[skill_path] = content_hash
                    restored_count += 1

            if restored_count > 0:
                middleware_logger.info(f"Restored {restored_count} persisted skills for user {self._user_id}")
        except Exception as e:
            # ✅ 修复4: error 级别日志（非 warning）
            middleware_logger.error(f"Skills restore failed for user {self._user_id}: {e}")
```

### 6.5 `tools_summarization.py` — 摘要监控（48行）

```python
"""中间件 5: 监控对话长度，超过 40 条消息时记录日志"""
from langchain.agents.middleware import AgentMiddleware, Runtime

class ToolsSummarizationMiddleware(AgentMiddleware):
    """补充框架内置的 SummarizationMiddleware，提供采购领域定制的监控"""
    def __init__(self):
        self.tools = []

    def before_agent(self, state, runtime):
        messages = state.get("messages", []) if isinstance(state, dict) else []
        if len(messages) > 40:
            middleware_logger.debug(f"Conversation length: {len(messages)} messages")
        return None
```

### 6.6 `memory_update.py` — 偏好自动提取（98行）

```python
"""
中间件 6: 对话结束后从消息中提取用户偏好 → store.aput() 持久化
"""
from langchain.agents.middleware import AgentMiddleware, Runtime


class MemoryUpdateMiddleware(AgentMiddleware):
    """
    after_agent: 从最近对话中提取用户偏好信号
    
    提取规则（基于关键词匹配，无需额外 LLM 调用）：
    - "以后都用饼图" → preferred_chart_type = "pie"
    - "用表格展示" → preferred_output = "table"
    
    工作原理：
    1. Agent 执行完成后，截取最近 3 条用户消息
    2. 用关键词匹配提取图表类型和输出格式偏好
    3. 将提取到的偏好持久化到 Store（跨会话保存）
    """
    
    # 图表类型关键词映射表
    # 用户说"饼图" → 存储为 "pie"
    CHART_KEYWORDS = {
        "饼图": "pie", 
        "柱状图": "bar", 
        "折线图": "line",
        "散点图": "scatter", 
        "雷达图": "radar", 
        "环形图": "donut",
    }
    
    # 输出格式关键词映射表
    OUTPUT_KEYWORDS = {
        "表格": "table", 
        "json": "json", 
        "markdown": "markdown",
    }

    def __init__(self, store=None, user_id="default_user"):
        """
        初始化中间件
        
        Args:
            store: StoreBackend 实例（用于持久化用户偏好）
            user_id: 用户ID（用于隔离不同用户的偏好数据）
        """
        self._store = store
        self._user_id = user_id
        self.tools = []  # LangChain 中间件要求

    def after_agent(self, state, runtime):
        """
        Agent 执行完成后调用：提取并持久化用户偏好
        
        执行流程：
        1. 检查 store 是否可用
        2. 从 state 中获取最近 10 条消息
        3. 过滤出最近 3 条用户消息
        4. 用关键词匹配提取偏好
        5. 如果有新偏好，持久化到 Store
        """
        # 如果没有 store，跳过（开发模式）
        if not self._store:
            return None
        
        # 从 state 中获取消息列表
        # state 可能是 dict 或对象，兼容处理
        messages = state.get("messages", []) if isinstance(state, dict) else []
        
        # 过滤出用户消息（最近 10 条中的后 3 条）
        # 只取用户发的消息，不包括 AI 回复
        user_messages = [
            m for m in messages[-10:] 
            if hasattr(m, "type") and m.type == "human"
        ][-3:]  # 取最近 3 条
        
        # 存储提取到的偏好（增量更新）
        preferences_updates = {}
        
        # 遍历用户消息，提取偏好
        for msg in user_messages:
            # 获取消息内容（兼容不同的消息对象格式）
            content = msg.content if hasattr(msg, "content") else str(msg)
            if not isinstance(content, str):
                continue
            
            # ----- 提取图表类型偏好 -----
            # 匹配规则：关键词 + "以后"/"默认" 出现在同一句话中
            # 例如："以后都用饼图" → 匹配到 "饼图" 和 "以后"
            for keyword, chart_type in self.CHART_KEYWORDS.items():
                if keyword in content and ("以后" in content or "默认" in content):
                    preferences_updates["preferred_chart_type"] = chart_type
            
            # ----- 提取输出格式偏好 -----
            # 匹配规则：关键词 + "用"/"格式" 出现在同一句话中
            # 例如："用表格展示" → 匹配到 "表格" 和 "用"
            for keyword, output_fmt in self.OUTPUT_KEYWORDS.items():
                if keyword in content and ("用" in content or "格式" in content):
                    preferences_updates["preferred_output"] = output_fmt
        
        # 如果有提取到新的偏好，持久化到 Store
        if preferences_updates:
            # 命名空间：("user-preferences", user_id) 隔离不同用户
            namespace = ("user-preferences", self._user_id)
            # 存储键值对：key="preferences", value=偏好字典
            # ❌ 问题：这里是同步 put，但 Store 接口通常是异步的 aput
            self._store.put(namespace, key="preferences", value=preferences_updates)
        
        # 返回 None 表示不修改 state
        return None
```

### 6.7 `sandbox_breaker.py` — 三态熔断器（121行）

```python
"""
中间件 7: 沙箱熔断器
三态模型：CLOSED(正常) → OPEN(熔断) → HALF_OPEN(探测) → CLOSED

工作原理：
- CLOSED（闭合）：正常调用，失败计数
- OPEN（断开）：直接拦截，不调用沙箱
- HALF_OPEN（半开）：允许单次调用探测，成功则恢复，失败则重回 OPEN
"""
import time
from langchain_core.messages import ToolMessage
from langchain.agents.middleware import AgentMiddleware, Runtime, ToolCallRequest


class SandboxCircuitBreakerMiddleware(AgentMiddleware):
    """
    连续 N 次沙箱工具调用失败 → 短路 → 降级响应
    仅拦截沙箱工具（execute, run_code 等），MCP/ERP 工具不受影响
    """
    
    # 需要熔断保护的沙箱工具名称集合
    # 这些工具依赖沙箱环境，容易因容器问题失败
    SANDBOX_TOOLS = {"execute", "run_code", "run_python", "shell", "bash"}

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 连续失败多少次后触发熔断（默认3次）
            recovery_timeout: 熔断后等待多少秒尝试恢复（默认60秒）
        """
        # 连续失败次数阈值
        self._failure_threshold = failure_threshold
        # 熔断恢复等待时间（秒）
        self._recovery_timeout = recovery_timeout
        # 当前连续失败计数
        self._failure_count = 0
        # 熔断器状态：CLOSED（闭合正常）/ OPEN（断开熔断）/ HALF_OPEN（半开探测）
        self._state = "CLOSED"
        # 最后一次失败的时间戳（用于计算恢复超时）
        self._last_failure_time = 0
        # 中间件工具列表（LangChain 要求）
        self.tools = []

    async def awrap_tool_call(self, request, handler):
        """
        拦截沙箱工具调用，实现熔断逻辑
        
        这是 LangChain 中间件的核心方法，在工具调用前后执行。
        
        Args:
            request: 工具调用请求（包含工具名、参数等）
            handler: 下一个处理器（最终会执行实际工具）
        
        Returns:
            工具调用结果或降级响应
        """
        # 获取工具名称
        tool_name = request.tool_call.get("name", "")
        
        # ----- 非沙箱工具直接放行 -----
        # 只拦截沙箱工具，MCP/ERP 工具不受熔断影响
        if tool_name.lower() not in self.SANDBOX_TOOLS:
            return await handler(request)

        # ============ 熔断器状态机 ============
        
        # ----- 状态：OPEN（熔断中） -----
        if self._state == "OPEN":
            # 检查是否已达到恢复超时时间
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                # 超时 → 进入半开状态，允许一次试探性调用
                self._state = "HALF_OPEN"
            else:
                # 熔断中 → 直接返回降级响应，不调用沙箱
                # 这可以快速失败，避免等待超时
                return ToolMessage(
                    content=f"[沙箱暂时不可用] 工具 '{tool_name}' 被熔断器拦截。",
                    tool_call_id=request.tool_call.get("id", ""),
                    status="error",
                )
        
        # ----- 尝试调用沙箱工具 -----
        try:
            # 执行实际的工具调用
            result = await handler(request)
            
            # ---- 调用成功 ----
            # 重置失败计数
            self._failure_count = 0
            # 恢复为闭合状态（正常）
            self._state = "CLOSED"
            return result
            
        except Exception as e:
            # ---- 调用失败 ----
            # 增加失败计数
            self._failure_count += 1
            # 记录失败时间
            self._last_failure_time = time.time()
            
            # 检查是否达到熔断阈值
            if self._failure_count >= self._failure_threshold:
                # 连续失败达到阈值 → 进入熔断状态
                self._state = "OPEN"
            
            # 返回错误信息（不抛出异常，让流程继续）
            return ToolMessage(
                content=f"[沙箱调用失败] {tool_name}: {str(e)[:200]}",
                tool_call_id=request.tool_call.get("id", ""),
                status="error",
            )
```

---

## 第7章 — 子Agent 配置

> 子Agent 是 Harness 架构中的任务委派机制。主Agent 负责理解用户意图并路由，复杂任务委派给专门的子Agent 执行。

### 7.1 `procurement_analyst.yaml` — 采购分析专家（115行）

**作用**：声明式配置分析子Agent 的名称、触发词、工具列表、上下文协议和系统提示词。

```yaml
name: procurement-analyst
description: >
  采购分析专家。触发词：分析、对比、统计、趋势、报表、图表、报告。
  负责对供应商、零部件、库存进行深度数据分析并生成可视化图表报告。

tools:
  - supplier_query      # 搜索供应商
  - supplier_page       # 分页查询供应商
  - supplier_get        # 获取供应商详情
  - part_search         # 搜索零部件
  - part_page           # 分页查询零部件
  - part_query          # 获取零部件详情
  - part_by_supplier    # 按供应商查产品
  - inventory_warning   # 库存预警
  - inventory_page      # 库存查询
  - inventory_check     # 库存盘点
  - order_search_details # 订单明细搜索
  - order_statistics    # 采购统计
  - order_page          # 订单分页
  - generate_chart      # 图表生成
  - web_search          # 网络搜索

# 上下文传递协议：定义主Agent委派时必须传递的字段
context_protocol:
  input_context:
    - field: user_id        # 必填：用户ID
      required: true
    - field: task_objective # 必填：分析目标
      required: true
    - field: user_preferences # 可选：用户偏好
      required: false
  output_format:
    type: structured_report  # 返回格式：结构化报告
    sections: [summary, data_table, charts, conclusions, recommendations]

system_prompt: |
  你是采购分析专家，专门负责摩托车零部件采购数据的深度分析和可视化。
  ## 分析流程（5步）
  第1步：明确分析目标
  第2步：数据采集（使用 MCP 工具）
  第3步：数据整理（清洗、分类、汇总）
  第4步：可视化生成（generate_chart）
  第5步：输出报告（Markdown 格式）
```

### 7.2 `procurement_order.yaml` — 采购订单专家（123行）

```yaml
name: procurement-order
description: >
  采购订单专家。触发词：下单、采购、订单、新增订单、修改订单、审批。

tools:
  - order_create        # 创建订单（需审批）
  - order_update        # 修改订单（需审批）
  - order_get           # 获取订单详情
  - order_page          # 分页查询
  - order_update_status # 状态变更
  - request_order_info  # 向用户请求补充信息
  - part_query          # 查零部件
  - part_search
  - supplier_query      # 查供应商
  - supplier_get

# 人工介入配置：这些工具被调用时自动暂停等待审批
interrupt_on:
  order_create:
    allowed_decisions: [approve, reject, edit]
    description: "采购订单创建审批"
  order_update:
    allowed_decisions: [approve, reject, edit]
    description: "采购订单修改审批"
  order_update_status:
    allowed_decisions: [approve, reject]
    description: "订单状态变更确认"

system_prompt: |
  你是采购订单专家，专门负责采购订单的全生命周期管理。
  ## 创建订单流程
  1. 整合信息（extracted_data + order_context）
  2. Schema校验（检查必填字段）
  3. 数据补充（request_order_info）
  4. 信息确认（展示摘要）
  5. 执行创建（order_create → 自动触发审批中断）
  ## 订单编号规则
  格式：PO + 年月日 + 3位序号，例如 PO20260727001
```

### 7.3 `src/agent/subagents/loader.py` — YAML 加载器（含输出契约校验）

**作用**：读取 YAML 配置 → 校验 → 工具名解析 → interrupt_on 解析 → **输出契约校验与注入** → 构造 SubAgent 实例。

**本次改造**：新增 `output_format` 契约校验，使 YAML 中声明的输出结构从"仅声明"变为"必须遵守的契约"，由主 Agent 评审器依据评审标准对子 Agent 输出做校验。

```python
"""
子Agent配置加载器
核心职责：
1. 读取 configs/*.yaml 并校验必填字段
2. 将 tools 字符串通过子串匹配映射为实际工具对象
3. 解析 interrupt_on 配置
4. 将 context_protocol 注入到主Agent系统提示词
"""
import yaml  # 导入 YAML 解析库，用于读取 .yaml 配置文件
from pathlib import Path  # 导入路径库，用于处理文件路径
from deepagents import SubAgent  # 导入子Agent类型（用于类型注解）
from langchain_core.tools import BaseTool  # 导入工具基类，用于类型注解
from ..log_utils import agent_logger  # 导入日志工具

# 配置文件目录：当前文件所在目录下的 configs 文件夹
CONFIGS_DIR = Path(__file__).parent / "configs"
# 子Agent配置的必填字段列表
# 每个子Agent配置文件必须包含这些字段
REQUIRED_FIELDS = ["name", "description", "system_prompt", "tools"]


def _validate_subagent_config(config: dict) -> bool:
    """校验子Agent配置必填字段
    
    检查配置字典是否包含所有必填字段，且字段值不为空
    
    Args:
        config: 从 YAML 文件加载的配置字典
    
    Returns:
        True 表示校验通过，False 表示校验失败
    """
    # 使用 all() 检查每个必填字段是否都存在且非空
    # config[field] 在字段存在且值非空时返回 True
    return all(field in config and config[field] for field in REQUIRED_FIELDS)


def _get_output_format(config: dict) -> dict | None:
    """提取子Agent的输出契约定义（兼容顶层 output_format 或 context_protocol.output_format）"""
    output_format = config.get("output_format")
    if isinstance(output_format, dict):
        return output_format
    protocol = config.get("context_protocol")
    if isinstance(protocol, dict):
        nested = protocol.get("output_format")
        if isinstance(nested, dict):
            return nested
    return None


def _validate_output_format(config: dict) -> bool:
    """校验子Agent的 output_format 契约结构（声明式输出契约的强校验）

    校验规则：
    - output_format 必须为 dict
    - 若含 sections 字段，必须是字符串列表
    """
    output_format = _get_output_format(config)
    if output_format is None:
        return True  # 未声明输出契约，不强制
    sections = output_format.get("sections")
    if sections is not None and (
        not isinstance(sections, list)
        or not all(isinstance(s, str) for s in sections)
    ):
        agent_logger.error(
            f"Invalid output_format.sections in {config.get('name')}: must be a list of strings"
        )
        return False
    return True


def build_output_contract_prompt(config: dict) -> str:
    """根据 output_format 生成输出契约提示词（注入子Agent system_prompt）。

    使 YAML 中声明的输出结构成为子Agent必须遵守的显式契约，
    并由主Agent的 RubricMiddleware 依据评审标准对子Agent输出做校验。
    """
    output_format = _get_output_format(config)
    if output_format is None:
        return ""

    fmt_type = output_format.get("type", "structured_report")
    sections = output_format.get("sections", [])
    fmt = output_format.get("format", "markdown")

    if not sections:
        return ""

    lines = [
        "\n\n## 输出契约（必须严格遵守）",
        f"你的最终返回结果必须符合以下结构化契约（类型：{fmt_type}，格式：{fmt}）：",
    ]
    for i, section in enumerate(sections, 1):
        lines.append(f"{i}. **{section}**")

    lines.append(
        "主Agent 将依据此契约对你的输出进行校验；缺失任一 section 将被视为不合格并触发返工。"
    )
    return "\n".join(lines)


def _parse_interrupt_on(config: dict) -> dict | None:
    """解析 YAML 中的 interrupt_on 配置为框架格式
    
    interrupt_on 用于配置人工审批流程：
    当子Agent调用某些工具时，需要等待人工审批才能继续
    
    YAML 格式示例：
    interrupt_on:
      delete_record:
        allowed_decisions: ["approve", "reject"]
        description: "删除记录需要管理员审批"
    
    Args:
        config: 子Agent配置字典
    
    Returns:
        解析后的 interrupt_on 字典，如果没有配置则返回 None
    """
    # 从配置中获取 interrupt_on 字段（可能不存在）
    raw = config.get("interrupt_on")
    
    # 如果没有配置，直接返回 None
    if not raw:
        return None
    
    # 解析后的结果字典
    parsed = {}
    
    # 遍历每个工具名称及其配置
    for tool_name, tool_config in raw.items():
        # 检查工具配置是否为字典格式
        if isinstance(tool_config, dict):
            # 构建框架需要的格式
            parsed[tool_name] = {
                # 允许的决策列表（默认 approve 和 reject）
                "allowed_decisions": tool_config.get("allowed_decisions", ["approve", "reject"]),
            }
            # 如果配置中有描述，也一并添加
            if "description" in tool_config:
                parsed[tool_name]["description"] = tool_config["description"]
    
    return parsed


def load_subagent_configs() -> list[dict]:
    """读取 configs/*.yaml，校验必填字段
    
    扫描配置目录下的所有 YAML 文件，加载并校验配置
    
    Returns:
        通过校验的配置列表（未通过校验的会被跳过并记录日志）
    """
    configs = []  # 存储通过校验的配置
    
    # 遍历 configs 目录下所有 .yaml 文件（按文件名排序）
    for yaml_file in sorted(CONFIGS_DIR.glob("*.yaml")):
        try:
            # 打开并读取 YAML 文件
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)  # 安全加载 YAML 内容
        except Exception as e:
            # 读取或解析失败，记录错误日志并跳过该文件
            agent_logger.error(f"Failed to load {yaml_file}: {e}")
            continue
        
        # 校验配置是否包含所有必填字段
        if config and _validate_subagent_config(config):
            # 校验通过，添加到结果列表
            configs.append(config)
            agent_logger.info(f"Loaded subagent config: {config['name']}")
        else:
            # 校验失败，记录警告日志
            agent_logger.warning(f"Invalid config in {yaml_file}: missing required fields")
    
    # 返回所有通过校验的配置
    return configs


def resolve_subagent_tools(configs: list[dict], all_tools: list[BaseTool]) -> list:
    """将 tools 字符串通过子串匹配映射为实际工具对象
    
    匹配规则：pattern in tool.name（子串包含匹配）
    例如："supplier" 会匹配 "supplier_query", "supplier_page", "supplier_get"
    
    这种设计允许用户在配置文件中只写 "supplier"，就能自动匹配所有相关工具
    
    Args:
        configs: 子Agent配置列表（来自 load_subagent_configs）
        all_tools: 所有可用工具的完整列表
    
    Returns:
        包含工具对象解析结果的子Agent规格列表（可直接用于创建 SubAgent）
    """
    subagents = []  # 存储解析后的子Agent规格
    
    # 遍历每个子Agent配置
    for config in configs:
        # 获取配置中的工具模式列表（字符串列表）
        tool_patterns = config.get("tools", [])
        
        # 存储匹配到的实际工具对象
        matched_tools = []
        
        # 遍历每个工具模式字符串
        for pattern in tool_patterns:
            # 遍历所有可用工具
            for tool in all_tools:
                # 检查模式字符串是否包含在工具名称中（子串匹配）
                # 且该工具尚未被添加（避免重复）
                if pattern in tool.name and tool not in matched_tools:
                    matched_tools.append(tool)
        
        # 解析 interrupt_on 配置
        interrupt_on = _parse_interrupt_on(config)

        # 校验 output_format 契约结构（非法则记录错误，仍继续创建但契约不注入）
        output_contract = ""
        if _validate_output_format(config):
            output_contract = build_output_contract_prompt(config)

        # 构建子Agent规格字典
        subagent_spec = {
            "name": config["name"],  # 子Agent名称
            "description": config["description"],  # 子Agent描述
            "system_prompt": config["system_prompt"] + output_contract,  # ★注入输出契约
            "tools": matched_tools,  # 匹配到的实际工具对象
        }
        
        # 如果有 interrupt_on 配置，添加到规格中
        if interrupt_on:
            subagent_spec["interrupt_on"] = interrupt_on
        
        # 添加到结果列表
        subagents.append(subagent_spec)
    
    return subagents


def get_delegation_context_prompt(configs: list[dict]) -> str:
    """生成主Agent的委派上下文提示词片段
    
    告诉主Agent在委派任务给子Agent时，应该传递哪些上下文信息。
    这个提示词会被注入到主Agent的系统提示词中。
    
    Args:
        configs: 子Agent配置列表
    
    Returns:
        格式化的上下文协议提示词字符串
    """
    sections = []  # 存储每个子Agent的协议说明
    
    # 遍历每个子Agent配置
    for config in configs:
        # 获取 context_protocol 配置
        protocol = config.get("context_protocol")
        
        # 如果没有配置上下文协议，跳过该子Agent
        if not protocol:
            continue
        
        # 获取输入上下文字段列表
        input_ctx = protocol.get("input_context", [])
        
        # 构建该子Agent的协议说明行
        lines = [f"\n### 委派给 {config['name']} 时的上下文传递要求"]
        
        # 遍历每个上下文字段定义
        for field_def in input_ctx:
            field = field_def.get("field", "")  # 字段名
            desc = field_def.get("description", "")  # 字段描述
            required = field_def.get("required", False)  # 是否必填
            
            # 根据是否必填添加标记
            marker = "**[必填]**" if required else "[可选]"
            
            # 添加字段说明行
            lines.append(f"- {marker} `{field}`: {desc}")
        
        # 将该子Agent的协议说明添加到节列表
        sections.append("\n".join(lines))
    
    # 如果有协议说明，组装成完整的提示词片段
    if sections:
        return "\n## 子Agent委派上下文协议\n" + "\n".join(sections)
    else:
        # 没有配置任何上下文协议，返回空字符串
        return ""
```

---

## 第8章 — 记忆与提示词

### 8.1 `src/agent/memory/prompts.py` — 系统提示词模板（90行）

**作用**：定义主 Agent 的系统提示词。这是 Agent 的"灵魂"——定义了它的角色、工作流程、核心能力和交互风格。

```python
"""主Agent系统提示词"""

MAIN_SYSTEM_PROMPT = """你是"智能采购助手"，基于 Harness Engineering 架构构建。
你能够帮助用户完成摩托车零部件采购管理中的各种任务。

## 当前用户信息
- 用户ID: {user_id}
- 用户名: {username}
- 用户偏好: {preferences}

## ❗ 核心工作流程（Harness 思想，必须严格遵守）

重要：对于简单问候、闲聊、简单问答（如"hi""你好""你是谁"），直接简洁回答即可，不需要规划。

仅对于需要调用工具或多步骤操作的复杂任务，遵循以下四阶段工作流：

### Step 1: 📝 Planning（规划）
- 使用 write_todos 工具创建结构化任务清单（不要在正文输出规划文本）
- 将任务拆分为可执行的步骤，每个步骤作为一条 todo 项
- 开始执行前将首条任务标记为 in_progress

### Step 2: ⚙️ Executing（执行）
- 按 todo 清单逐步执行，完成一步立即用 write_todos 标记该步为 completed
- 调用工具时简要说明正在做什么
- 格式："✅ 已获取 36 家供应商数据"

### Step 3: 🔍 Review（审查）
- 系统评审器会自动对照评审标准检查你的执行结果
- 若评审未通过，请依据反馈修正后重新输出

### Step 4: 📊 Result（结果）
- 最终结构化输出结果
- 提供下一步建议

## 核心能力
1. 供应商管理 - 查询、搜索、分析
2. 零部件管理 - 搜索、筛选、详情
3. 采购订单管理 - 创建(需审批)、修改、跟踪
4. 库存管理 - 预警、盘点、入/出库
5. 数据分析与图表 - 26种可视化
6. 网络搜索与Skill下载

## 工作规范
1. 复杂分析 → 委派 procurement-analyst
2. 订单操作 → 委派 procurement-order
3. 创建/修改订单前必须获得用户确认
4. 默认 Markdown 格式，金额保留2位小数
"""
```

**设计要点**：
- `{user_id}` / `{username}` / `{preferences}` 是模板变量，在 `main_agent.py` 中通过 `.format()` 填充
- Harness 4 步工作流（Planning → Executing → Review → Result）是核心思想
- **规划改用 `write_todos` 工具**（结构化 todo），而非在正文输出规划文本——与 `TodoListMiddleware` 对齐，供 `chat.py` 从 state 读取
- **审查由系统评审器自动完成**（`RubricMiddleware`），不再要求 LLM 输出"审查"自述文本
- 简单问候不需要规划，避免"hi"也输出任务列表

---

### 8.2 `src/agent/memory/AGENTS.md` — 全局操作手册（83行）

**作用**：Agent 的全局记忆文件，定义了工具使用规范、子Agent 委派模板、输出格式要求。

```markdown
# Agent 全局操作手册

## 角色定义
你是码士集团的智能采购助手，专门服务于摩托车零部件采购管理业务。

## 工具使用规范

### MCP 工具（ERP 系统交互）
- `supplier_query`: 按名称搜索供应商
- `supplier_page`: 分页查询供应商
- `part_query`: 获取零部件详情
- `part_search`: 搜索零部件
- `order_create`: 创建采购订单（需审批）
- `order_update`: 更新订单（需审批）
- `inventory_warning`: 库存预警
- ... 共 16 个 MCP 工具

### 自定义工具
- `generate_chart`: 26种图表
- `web_search`: 网络搜索
- `request_order_info`: 订单信息补充

## 子Agent委派模板

### 委派给 procurement-analyst
触发条件："分析"、"对比"、"统计"、"图表"等关键词
委派格式：task(agent="procurement-analyst", prompt="用户ID: ... 任务: ...")

### 委派给 procurement-order
触发条件："下单"、"采购"、"订单"等关键词

## 输出格式要求
- Markdown 格式
- 金额保留2位小数
- 日期格式：yyyy-MM-dd
```

**与 prompts.py 的区别**：
- `prompts.py` 是系统提示词（每次对话都注入到 LLM）
- `AGENTS.md` 是全局记忆（通过 deepagents 的 memory 参数加载，作为长期记忆）

---

## 第9章 — Agent 核心组装

> 这是整个项目最重要的文件——`main_agent.py`。它把前面所有章节的组件组装成一个完整的 Agent。

### 9.1 `src/agent/mcp_tools_bean.py` — 工具分类（67行）

```python
"""MCP 工具分类 Bean — 将工具按用途分组"""

# 分析子Agent使用的工具名关键字
ANALYST_TOOL_PATTERNS = [
    "supplier_query", "supplier_page", "supplier_get",
    "part_search", "part_page", "part_query", "part_by_supplier",
    "inventory_warning", "inventory_page", "inventory_check",
    "order_search_details", "order_statistics", "order_page",
    "generate_chart", "web_search",
]

# 订单子Agent使用的工具名关键字
ORDER_TOOL_PATTERNS = [
    "order_create", "order_update", "order_get", "order_page",
    "order_update_status", "request_order_info",
    "part_query", "part_search", "supplier_query", "supplier_get",
]

def classify_tools(all_tools):
    """将工具按用途分类"""
    tool_map = {t.name: t for t in all_tools}
    analyst_tools = [t for p in ANALYST_TOOL_PATTERNS for n, t in tool_map.items() if p in n]
    order_tools = [t for p in ORDER_TOOL_PATTERNS for n, t in tool_map.items() if p in n]
    return {"analyst_tools": analyst_tools, "order_tools": order_tools, "all_tools": all_tools}
```

### 9.2 `src/agent/middleware_config.py` — 子Agent中间件工厂（22行）

```python
"""子Agent中间件工厂"""
from deepagents.middleware import SummarizationToolMiddleware

def get_analyst_middleware() -> list:
    """分析子Agent需要摘要工具来压缩大量数据结果"""
    return [SummarizationToolMiddleware()]

def get_order_middleware() -> list:
    """订单子Agent也需要摘要能力"""
    return [SummarizationToolMiddleware()]
```

### 9.3 `src/agent/main_agent.py` — 主 Agent 组装（347行）

**这是整个项目最核心的文件**。它按照 7 步顺序组装 Agent，包含 **沙箱初始化** 和 **Skills 加载** 两大新增功能。

```python
"""
主入口：create_main_agent() + precompute_agent_context()
DeepAgent 核心组装 — 严格遵循 Harness Engineering 架构
"""
import io, tarfile, fnmatch
from deepagents import create_deep_agent, RubricMiddleware  # ★评审器
from deepagents.backends import CompositeBackend, StoreBackend, LocalShellBackend
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from .backends.custom_opensandbox import DockerSandboxBackend
from .config import get_llm, SKILLS_STORE_NAMESPACE, INTERRUPT_ON_TOOLS, MAX_MODEL_CALLS, MAX_TOOL_CALLS
from .schema import ProcurementContext
from .memory.prompts import MAIN_SYSTEM_PROMPT

PROJECT_ROOT = Path(__file__).parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "src" / "skills"
MEMORY_DIR = Path(__file__).parent / "memory"


def _upload_project_to_sandbox(sandbox):
    """将项目文件上传到沙箱 /workspace/src/ 目录（跳过 .git/node_modules 等）"""
    skip_patterns = [".git", "__pycache__", "node_modules", ".next", "*.pyc", ...]
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
        for file_path in sorted(PROJECT_ROOT.rglob("*")):
            if file_path.is_file() and not _should_skip(rel)
                tar.add(str(file_path), arcname=rel)
    sandbox._container.put_archive("/workspace/src", tar_stream.read())
    agent_logger.info(f"Project uploaded: /workspace/src (N files, X MB)")


def _load_skills_prompt(skills_dir):
    """手动加载所有 SKILL.md，注入 system prompt（绕过框架中文路径 bug）"""
    for skill_md in skills_dir.rglob("SKILL.md"):
        content = skill_md.read_text(encoding="utf-8")
        skill_sections.append(f"### Skill: {rel_path}\n{content}")
    return "\n\n## 可用技能 (Skills)\n\n" + "\n\n".join(skill_sections)


async def precompute_agent_context(user_id, username, store=None) -> ProcurementContext:
    """预计算上下文：从 Store 加载用户偏好"""
    ...


def create_main_agent(user_context=None, checkpointer=None, store=None):
    """
    创建主 Agent 实例 — 7 步组装（含沙箱初始化 + Skills 加载）
    """
    # ===== 第1步：LLM =====
    llm = get_llm()

    # ===== 第2步：CompositeBackend + 沙箱初始化 =====
    try:
        sandbox_backend = DockerSandboxBackend(container_name="erp-sandbox")

        # ⚡ 沙箱初始化：创建目录 + 上传项目文件
        sandbox_backend.execute("mkdir -p /workspace/charts /workspace/output /workspace/data /skills /src/skills")
        _upload_project_to_sandbox(sandbox_backend)

        # 注册到全局持有器，供所有工具访问
        from .backends.sandbox_holder import set_sandbox
        set_sandbox(sandbox_backend)
    except Exception:
        sandbox_backend = LocalShellBackend(virtual_mode=True)  # 回退方案

    def backend_factory(rt):
        routes = {}
        if store:
            routes["/memories/"] = StoreBackend(namespace=lambda _rt: (user_context.user_id,))
            routes["/persisted-skills/"] = StoreBackend(namespace=lambda _rt: SKILLS_STORE_NAMESPACE)
        return CompositeBackend(default=sandbox_backend, routes=routes)

    # ===== 第3步：加载工具 =====
    from .tools.mcp_client import load_mcp_tools_sync
    from .tools.chart_generator import generate_chart
    from .tools.web_search import web_search
    from .tools.web_fetch import web_fetch, install_skill
    from .tools.hitl_tools import request_order_info

    mcp_tools = load_mcp_tools_sync()  # 23 个 ERP 工具
    custom_tools = [generate_chart, web_search, web_fetch, install_skill, request_order_info]
    all_tools = mcp_tools + custom_tools  # 共 28 个工具

    # ===== 第4步：加载子Agent配置 =====
    from .subagents.loader import load_subagent_configs, resolve_subagent_tools, get_delegation_context_prompt
    subagent_configs = load_subagent_configs()  # 读取 YAML
    subagents = resolve_subagent_tools(subagent_configs, all_tools)  # 字符串 → 工具对象
    delegation_prompt = get_delegation_context_prompt(subagent_configs)  # 委派协议

    # ===== 第5步：组装中间件栈 =====
    from .middlewares.sandbox_health import SandboxHealthMiddleware
    from .middlewares.context_injection import ContextInjectionMiddleware
    from .middlewares.skills_sync import SkillsSyncMiddleware
    from .middlewares.user_skills_restore import UserSkillsRestoreMiddleware
    from .middlewares.tools_summarization import ToolsSummarizationMiddleware
    from .middlewares.memory_update import MemoryUpdateMiddleware
    from .middlewares.sandbox_breaker import SandboxCircuitBreakerMiddleware
    from .harness import HarnessPhaseMiddleware, load_harness_config  # ★Harness 核心

    # 读取 Harness DSL 配置中的评审迭代上限
    _harness_config = load_harness_config()
    _review_max_iterations = _harness_config.get("review", {}).get("max_iterations", 3)

    middlewares = [
        SandboxHealthMiddleware(),                                    # 1. 沙箱健康
        HarnessPhaseMiddleware(),                                     # 2. ★阶段状态机 + rubric 注入
        ContextInjectionMiddleware(user_context=user_context),        # 3. 上下文注入
        SkillsSyncMiddleware(skills_dir=SKILLS_DIR),                  # 4. 技能同步
        UserSkillsRestoreMiddleware(store=store, user_id=user_context.user_id),  # 5. 技能恢复
        ToolsSummarizationMiddleware(),                               # 6. 摘要监控
        MemoryUpdateMiddleware(store=store, user_id=user_context.user_id),      # 7. 偏好提取
        SandboxCircuitBreakerMiddleware(failure_threshold=3),         # 8. 熔断器
        # ★ Harness 评审器：grader 子Agent 结构化打分，needs_revision 打回重做
        RubricMiddleware(model=llm, max_iterations=_review_max_iterations),
        ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS),          # 框架内置：LLM调用上限
        ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS),            # 框架内置：工具调用上限
    ]

    # ===== 第6步：构建系统提示词 =====
    system_prompt = MAIN_SYSTEM_PROMPT.format(
        user_id=user_context.user_id,
        username=user_context.username,
        preferences=str(user_context.preferences) if user_context.preferences else "无特殊偏好",
    )
    if delegation_prompt:
        system_prompt += delegation_prompt  # 注入子Agent委派协议

    # ===== 第6.5步：手动加载 Skills 到 system prompt =====
    # ❌ 框架内置 SkillsMiddleware 无法处理含中文路径
    # ✅ 改用 _load_skills_prompt() 手动注入 → system_prompt
    skills_prompt = _load_skills_prompt(SKILLS_DIR)
    if skills_prompt:
        system_prompt += skills_prompt

    # ===== 第7步：创建 Agent =====
    # ⚡ skills=None 禁用框架 SkillsMiddleware（避免 path_not_found）
    agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        system_prompt=system_prompt,
        middleware=middlewares,
        subagents=subagents if subagents else None,
        skills=None,                           # ⚡ 禁用框架内置加载器
        memory=[str(MEMORY_DIR / "AGENTS.md")],
        backend=backend_factory,               # 三层路由后端
        interrupt_on=INTERRUPT_ON_TOOLS,       # 中断配置（订单审批）
        checkpointer=checkpointer,             # 会话持久化
        store=store,                           # 跨会话存储
        name="procurement-main-agent",
    )
    return agent
```

**Skills 加载方案对比**：

| 维度 | 旧版（`skills=["path"]`） | 新版（`skills=None`） |
|------|--------------------------|----------------------|
| 加载器 | 框架 `SkillsMiddleware` | `_load_skills_prompt()` 手动注入 |
| 中文路径 | ❌ `path_not_found` | ✅ 正常工作 |
| 文件同步 | 无 | `SkillsSyncMiddleware` → 沙箱 `/skills/` |
| 框架警告 | ❌ 每次启动报错 | ✅ 完全消除 |

**Harness 架构思想在代码中的体现**：
1. **Planning → Executing → Review → Result**：不再是 prompt 软约束，而是 `HarnessPhaseMiddleware` 写入的 graph state 结构化字段 + `RubricMiddleware` 评审回路
2. **中间件栈**：7 个自定义中间件 + Harness 阶段状态机 + 评审器，提供可扩展的 before/after/wrap 钩子
3. **子Agent 委派**：通过 YAML 声明式配置，主Agent 自动路由；输出契约由 loader 校验注入
4. **CompositeBackend**：不同路径路由到不同后端（沙箱/Store）
5. **HITL**：`interrupt_on` 配置让危险操作必须经过人工审批

**评审回路（Review Loop）**：`RubricMiddleware` 收到 `HarnessPhaseMiddleware` 注入的 rubric 后，用独立的 grader 子 Agent 对照执行记录逐条打分；判定 `needs_revision` 时自动注入反馈并 `jump_to=model` 重做，最多迭代 `max_iterations`（DSL 可配）次，形成真正的 Review 回路。

---

## 第10章 — Web API 层

> Web API 层是前端与 Agent 之间的桥梁。核心是 SSE 流式对话端点，实时将 Agent 的执行过程（token、工具调用、中断）推送给前端。

### 10.1 `src/api_view/web_config.py` — MongoDB 连接（35行）

```python
"""MongoDB 连接配置 — Motor 异步客户端"""
from motor.motor_asyncio import AsyncIOMotorClient
from ..agent.env_utils import get_env

MONGODB_URI = get_env("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = get_env("MONGODB_DB_NAME", "erp_agent")
_client = None

def get_mongo_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
    return _client

def get_db():
    return get_mongo_client()[MONGODB_DB_NAME]

async def close_mongo_client():
    global _client
    if _client:
        _client.close()
        _client = None
```

### 10.2 `src/api_view/agent_loader.py` — Agent 单例管理器（MongoDB 持久化）

**旧版问题**：使用 `MemorySaver()` + `InMemoryStore()`，服务重启后所有会话数据和用户偏好全部丢失。

**新版方案**：使用 `MongoDBSaver` + 自定义 `MongoDBStore`，生产级持久化。

```python
"""AgentLoader 单例 — MongoDB 持久化版"""
import uuid
from ..agent.schema import ProcurementContext
from .web_config import get_db, MONGODB_URI, MONGODB_DB_NAME

class AgentLoader:
    """Agent 加载器单例
    
    核心职责：
    1. 延迟初始化 Agent（首次请求时创建）
    2. 持有 MongoDB checkpointer + MongoDB store
    3. 消息持久化（display_messages → MongoDB）
    4. 会话管理（CRUD）
    """
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self):
        """延迟初始化 Agent（MongoDB 生产级存储）"""
        if self.agent is not None: return

        # ✅ 生产级存储：MongoDB 持久化
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient
        from .mongodb_store import MongoDBStore

        mongo_client = MongoClient(MONGODB_URI)
        self._checkpointer = MongoDBSaver(mongo_client)  # 会话状态持久化
        self._store = MongoDBStore(                         # 跨会话存储
            uri=MONGODB_URI,
            db_name=MONGODB_DB_NAME,
            collection_name="langgraph_store",
        )

        from ..agent.main_agent import create_main_agent
        self.agent = create_main_agent(
            user_context=ProcurementContext(),
            checkpointer=self._checkpointer,
            store=self._store,
        )

agent_loader = AgentLoader()  # 全局单例
```

**本次改造新增**：`save_harness_trace` 方法 — 将 Harness 阶段流转 trace 持久化到 MongoDB `harness_traces` 集合，支持事后审计"哪一步卡住了"。

```python
async def save_harness_trace(self, thread_id: str, trace: list):
    """保存 Harness 阶段流转 trace 到 MongoDB（可观测/审计）

    记录 Planning → Executing → Review → Result 各阶段的流转时间线，
    以及评审器的结构化判定结果。
    """
    db = get_db()
    await db.harness_traces.update_one(
        {"thread_id": thread_id},
        {"$set": {"trace": trace, "updated_at": datetime.now().isoformat()}},
        upsert=True,
    )
```

`delete_conversation` 同步清理 `harness_traces` 集合，保证删除会话时 trace 一并清除。

**新增文件**：`src/api_view/mongodb_store.py` — 自定义 `BaseStore` 的 MongoDB 实现，支持 `get`/`put`/`search`/`delete`/`list_namespaces` 接口。

**与旧版的关键区别**：
- `MemorySaver()` → `MongoDBSaver(MongoClient)` — 会话状态重启不丢失
- `InMemoryStore()` → `MongoDBStore(MongoDB)` — 用户偏好/技能跨会话持久化
- 新增 `harness_traces` 集合 — 阶段流转可观测 trace

### 10.3 `src/api_view/api/history.py` — 历史会话 CRUD（31行）

```python
"""历史会话管理 — 会话列表 / 消息查询 / 会话删除"""
from fastapi import APIRouter, Query
from ..agent_loader import agent_loader

router = APIRouter(prefix="/api/history", tags=["history"])

@router.get("")
async def list_conversations(user_id: str = Query(default="default_user")):
    """获取会话列表"""
    return {"conversations": await agent_loader.get_conversations(user_id)}

@router.get("/{thread_id}/messages")
async def get_messages(thread_id: str):
    """获取指定会话的消息列表"""
    return {"thread_id": thread_id, "messages": await agent_loader.get_display_messages(thread_id)}

@router.delete("/{thread_id}")
async def delete_conversation(thread_id: str):
    """删除会话"""
    await agent_loader.delete_conversation(thread_id)
    return {"success": True}
```

### 10.4 `src/api_view/api/chat.py` — SSE 流式对话（核心）

**这是整个 Web 层最核心的文件**。它实现了：
- SSE 流式响应（逐 token 推送）
- 中断检测（HITL 审批/信息补充）
- **结构化 Harness 阶段读取（替代正则猜测）**
- **结构化 TODO 列表读取（替代正则提取编号）**
- **评审结果读取（custom 流 rubric 事件）**
- 阶段流转 trace 收集 + 消息持久化

```python
"""
核心 SSE 流式对话 + 中断检测 + 中断恢复 + 展示消息持久化

关键设计：
- 三模式流: stream_mode=["messages", "values", "custom"], subgraphs=True
- 阶段流转从 values 流的 state.phase 读取（HarnessPhaseMiddleware 写入）
- todo 列表从 values 流的 state.todos 读取（TodoListMiddleware 写入）
- 评审结果从 custom 流的 rubric_evaluation_start/end 事件读取
- SSE 事件协议: thinking / token / tool_start / tool_args / tool_result / tool_end
  / phase / todo_update / review_result / interrupt / done
"""
import json, uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from ..agent_loader import agent_loader
from ...agent.schema import ChatRequest, ResumeRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Harness 阶段 → 前端展示文案
PHASE_LABELS = {
    "planning": "📝 规划中", "executing": "⚙️ 执行中",
    "reviewing": "🔍 审查中", "result": "📊 已完成", "thinking": "💭 思考中",
}


def sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件（严格遵循 event:/data: 协议）"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat_response(message, thread_id, user_id="default_user", resume_data=None):
    """核心流式响应生成器

    三模式流（subgraphs=True 时输出为 3-tuple）：
    - (namespace, "values", data): 读 phase/todos + 检测中断
    - (namespace, "messages", data): 逐 token + 工具调用
    - (namespace, "custom", data): 评审器 rubric_evaluation_start/end 事件
    """
    config = agent_loader.create_config(thread_id)
    display_messages = await agent_loader.get_display_messages(thread_id)

    if resume_data:
        current_input = Command(resume=resume_data)  # 中断恢复
    else:
        display_messages.append({"id": str(uuid.uuid4()), "role": "user", "content": message})
        current_input = {"messages": [{"role": "user", "content": message}]}

    assistant_content = ""
    tool_calls_buffer = []
    phase = "thinking"
    last_phase = "thinking"       # 上次已发射阶段（去重）
    last_todos_sig = None         # 上次 todo 列表签名（去重）
    harness_trace = []            # Harness 阶段流转 trace（可观测）

    yield sse_event("thinking", {"status": "start"})

    async for namespace, chunk_type, chunk in agent_loader.agent.astream(
        input=current_input, config=config,
        stream_mode=["messages", "values", "custom"], subgraphs=True,
    ):
        # ===== values 流：结构化阶段/todo + 中断检测 =====
        if chunk_type == "values":
            # ★ 阶段流转（来自 HarnessPhaseMiddleware 写入的 state.phase）
            new_phase = chunk.get("phase")
            if new_phase and new_phase != last_phase:
                last_phase = new_phase
                phase = new_phase
                harness_trace.append({"type": "phase", "phase": new_phase,
                                      "label": PHASE_LABELS.get(new_phase, new_phase),
                                      "timestamp": datetime.now().isoformat()})
                yield sse_event("phase", {"phase": new_phase, "label": PHASE_LABELS.get(new_phase, new_phase)})

            # ★ 结构化 todo（来自 TodoListMiddleware 的 write_todos 状态）
            todos = chunk.get("todos")
            if todos is not None:
                todos_sig = json.dumps(todos, ensure_ascii=False, sort_keys=True)
                if todos_sig != last_todos_sig:
                    last_todos_sig = todos_sig
                    plan_items = [{"id": f"todo-{i}", "content": t.get("content",""),
                                   "status": t.get("status","pending")}
                                  for i, t in enumerate(todos)]
                    if plan_items:
                        yield sse_event("todo_update", {"phase": "planning", "todos": plan_items})

            # 中断检测
            if chunk.get("interrupts"):
                # 判断中断类型 → 发射 interrupt SSE 事件
                # 保存消息 + trace → done(interrupted=True) → return
                ...

        # ===== custom 流：评审器结构化事件 =====
        if chunk_type == "custom":
            ev_type = chunk.get("type", "")
            if ev_type == "rubric_evaluation_start":
                if phase != "reviewing":
                    phase = "reviewing"
                    yield sse_event("phase", {"phase": "reviewing", "label": "🔍 审查中"})
            elif ev_type == "rubric_evaluation_end":
                review_data = {"verdict": chunk.get("result",""),
                               "explanation": chunk.get("explanation",""),
                               "criteria": chunk.get("criteria", []),
                               "iteration": chunk.get("iteration", 0)}
                harness_trace.append({"type": "review", **review_data,
                                      "timestamp": datetime.now().isoformat()})
                yield sse_event("review_result", review_data)

        # ===== messages 流：token + 工具调用 =====
        if chunk_type == "messages":
            token = chunk[0] if isinstance(chunk, (list, tuple)) else chunk
            tool_call_chunks = getattr(token, "tool_call_chunks", None)

            # 工具调用开始 → tool_start / tool_args
            if tool_call_chunks:
                for tc in tool_call_chunks:
                    if tc.get("name"):
                        yield sse_event("tool_start", {"name": tc["name"], "id": tc.get("id")})
                    if tc.get("args"):
                        yield sse_event("tool_args", {"args": tc["args"]})
                continue

            # 工具结果 → tool_result / tool_end
            if getattr(token, "type", "") == "tool":
                yield sse_event("tool_result", {"name": token.name, "content": str(token.content)[:2000]})
                yield sse_event("tool_end", {"id": getattr(token, "tool_call_id", "")})
                continue

            # 文本 token → token 事件（阶段不再靠正则，直接从 state 读）
            content = getattr(token, "content", "")
            if content and isinstance(content, str):
                assistant_content += content
                source = "analyst" if "analyst" in str(namespace) else "main"
                yield sse_event("token", {"content": content, "source": source})

    # 流结束 → 保存消息 + trace → 保存会话 → done
    await agent_loader.save_display_messages(thread_id, display_messages)
    await agent_loader.save_harness_trace(thread_id, harness_trace)
    await agent_loader.save_conversation(thread_id, user_id, title)
    yield sse_event("done", {"thread_id": thread_id, "interrupted": False})


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式对话端点"""
    await agent_loader.initialize()
    thread_id = request.thread_id or agent_loader.generate_thread_id()
    return StreamingResponse(
        stream_chat_response(message=request.message, thread_id=thread_id, user_id=request.user_id),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},  # 禁用 Nginx 缓冲
    )

@router.post("/{thread_id}/resume")
async def chat_resume(thread_id: str, request: ResumeRequest):
    """中断恢复端点 — 用户提交审批/补充信息后调用"""
    return StreamingResponse(
        stream_chat_response(message="", thread_id=thread_id, resume_data=request.resume),
        media_type="text/event-stream",
    )
```

**关键设计变化（本次改造）**：

| 维度 | 旧版（正则猜测） | 新版（结构化 state） |
|------|------------------|----------------------|
| 阶段检测 | `re.search(r'(任务规划\|Planning)', 文本)` | 读 `state.phase`（`HarnessPhaseMiddleware` 写入） |
| todo 列表 | `re.findall(r'\d+[.、)]\s*...', 文本)` | 读 `state.todos`（`TodoListMiddleware` 写入） |
| Review 检测 | `marker in content`（"审查"/"🔍"） | 读 `custom` 流 `rubric_evaluation_end` 事件 |
| stream_mode | `["messages", "values"]` | `["messages", "values", "custom"]` |
| 可观测性 | 无 | `harness_trace` 持久化到 MongoDB |

**SSE 事件协议完整列表**：

| 事件 | data | 触发时机 |
|------|------|----------|
| `thinking` | `{status: "start"/"end"}` | LLM 开始/结束思考 |
| `token` | `{content, source}` | 每个文本 token |
| `tool_start` | `{name, id}` | 工具调用开始 |
| `tool_args` | `{args}` | 工具参数（流式） |
| `tool_result` | `{name, content}` | 工具返回结果 |
| `tool_end` | `{id}` | 工具调用结束 |
| `phase` | `{phase, label}` | Harness 阶段变化（结构化） |
| `todo_update` | `{phase, todos}` | 任务规划更新（结构化） |
| `review_result` | `{verdict, explanation, criteria, iteration}` | ★评审器判定结果 |
| `interrupt` | `{interrupt_type, ...}` | 中断（审批/补充） |
| `done` | `{thread_id, interrupted}` | 流结束 |
| `error` | `{message}` | 错误 |

### 10.5 `src/api_view/web_main.py` — FastAPI 入口（85行）

```python
"""FastAPI 应用入口 — CORS 全开、路由注册、生命周期管理"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .api.chat import router as chat_router
from .api.history import router as history_router
from .web_config import close_mongo_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    web_logger.info("Starting ERP Agent Web Server...")
    yield
    await close_mongo_client()  # 关闭 MongoDB

app = FastAPI(title="DeepAgent 智能采购助手", lifespan=lifespan)

# CORS 全开（开发环境）
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 注册路由
app.include_router(chat_router)    # /api/chat/*
app.include_router(history_router) # /api/history/*

# 文件下载端点（图表 PNG）
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "download"
@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = DOWNLOAD_DIR / filename
    return FileResponse(path=str(file_path), filename=filename)

@app.get("/")
async def root():
    return {"message": "DeepAgent 智能采购助手 API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 附录 — 完整执行流程

### A.1 一次对话的完整调用链

用户输入："帮我分析所有供应商的供货能力"

```
1. 前端 → POST /api/chat/stream {message: "帮我分析...", user_id: "user-001"}
2. web_main.py → chat_router → chat_stream()
3. chat.py → agent_loader.initialize() → 确保 Agent 已创建
4. chat.py → stream_chat_response() → yield thinking(start)
5. chat.py → agent.astream(input, stream_mode=["messages","values"])
6. main_agent.py → 中间件 before_agent() 依次执行:
   ① SandboxHealthMiddleware → ping 沙箱
   ② ContextInjectionMiddleware → 注入 user_id/preferences
   ③ SkillsSyncMiddleware → 同步技能文件
   ④ UserSkillsRestoreMiddleware → 恢复持久化技能
   ⑤ ToolsSummarizationMiddleware → 检查上下文长度
7. LLM 输出 Planning 文本
8. chat.py → 正则检测 → yield phase(planning) + todo_update
9. LLM 决定委派 → tool_call: task(agent="procurement-analyst")
10. chat.py → yield tool_start + tool_args
11. 子Agent 开始执行:
    ① supplier_page(size=100) → MCP → HTTP → Java ERP → 返回供应商列表
    ② generate_chart(bar, data) → matplotlib → PNG
    ③ 输出分析报告
12. chat.py → yield token(子Agent的token) + tool_result
13. LLM 输出 Review + Result
14. chat.py → yield phase(reviewing) + phase(done)
15. 中间件 after_agent():
    ⑥ MemoryUpdateMiddleware → 提取偏好 → store.put()
16. chat.py → save_display_messages() → MongoDB
17. chat.py → save_conversation() → MongoDB
18. chat.py → yield done(thread_id, interrupted=False)
```

### A.2 启动命令与依赖关系

```bash
# 启动顺序（严格按依赖）
# 1. MongoDB（Docker）
docker start erp-mongo

# 2. MCP Server（无外部依赖，先启动）
python -m uvicorn src.mcp_server.server_main:app --port 9000

# 3. Web API Server（依赖 MCP Server + MongoDB）
python -m uvicorn src.api_view.web_main:app --port 8000

# 4. Frontend（依赖 Web API）
cd frontend && npm run dev
```

### A.3 中间件执行时序图

```
用户请求
    │
    ▼
┌─────────────────────────────┐
│ ① SandboxHealthMiddleware   │  before_agent: ping 沙箱
├─────────────────────────────┤
│ ② ContextInjectionMiddleware│  before_agent: 注入用户上下文
├─────────────────────────────┤
│ ③ SkillsSyncMiddleware      │  before_agent: 同步技能
├─────────────────────────────┤
│ ④ UserSkillsRestore         │  before_agent: 恢复持久化技能
├─────────────────────────────┤
│ ⑤ Summarization             │  before_agent: 检查上下文长度
├─────────────────────────────┤
│ ⑥ MemoryUpdate              │  after_agent: 提取偏好
├─────────────────────────────┤
│ ⑦ SandboxCircuitBreaker     │  wrap_tool_call: 熔断保护
├─────────────────────────────┤
│ ModelCallLimit              │  框架内置: LLM 调用上限
├─────────────────────────────┤
│ ToolCallLimit               │  框架内置: 工具调用上限
└─────────────────────────────┘
    │
    ▼
  Agent 执行
```

### A.4 HITL 中断/恢复流程

```
用户: "帮我创建一个采购订单"
    │
    ▼
主Agent → 委派 procurement-order
    │
    ▼
子Agent → 提取订单信息 → 发现缺少 partId
    │
    ▼
子Agent → 调用 request_order_info()
    │
    ▼
hitl_tools.py → interrupt({type: "order_info_request", missing: ["partId"]})
    │
    ▼
LangGraph 暂停执行
    │
    ▼
chat.py → 检测 values.interrupts → yield SSE interrupt 事件
    │
    ▼
前端 → 显示补充信息输入框
    │
    ▼
用户输入: "零件ID=5 数量100 单价25.5"
    │
    ▼
前端 → POST /api/chat/{thread_id}/resume {supplement: "零件ID=5..."}
    │
    ▼
chat.py → stream_chat_response(resume_data=...) → Command(resume=...)
    │
    ▼
LangGraph 恢复执行 → interrupt() 返回用户输入
    │
    ▼
hitl_tools.py → parse_supplement_text() → validate_order_data() → 数据完整
    │
    ▼
子Agent → 调用 order_create() → 触发 interrupt_on 审批中断
    │
    ▼
前端 → 显示审批卡片 → 用户点击"批准"
    │
    ▼
前端 → POST /resume {decisions: [{type: "approve"}]} → 订单创建成功
```

---

## 总结

本文档按照「基础设施 → MCP网关 → 工具层 → 沙箱 → 中间件 → 子Agent → 记忆 → 核心组装 → Web API」的顺序，逐文件解析了整个 Python 后端代码。

**核心文件阅读顺序推荐**：
1. `config.py` → 了解所有配置
2. `main_agent.py` → 了解 Agent 如何组装（含沙箱初始化、Skills 加载、Harness 中间件）
3. `harness.py` → ★了解 Harness 阶段状态机 + rubric 注入 + 评审回路
4. `harness_config.yaml` → ★了解声明式工作流配置（四阶段/评审标准）
5. `custom_opensandbox.py` → 了解沙箱后端（30+ 方法、文件操作、多语言运行时）
6. `sandbox_holder.py` → 了解工具如何全局访问沙箱
7. `chart_generator.py` → 了解沙箱内代码执行模式
8. `chat.py` → 了解 SSE 流式对话 + 结构化阶段读取
9. `skills_sync.py` → 了解技能增量同步机制

**关键设计模式**：
- **Harness 工作流**：Planning → Executing → Review → Result 已从 prompt 软约束升级为 graph state 结构化字段（`HarnessPhaseMiddleware`）+ 评审回路（`RubricMiddleware`）
- **沙箱优先**：所有代码执行/文件生成强制在 Docker 沙箱内，宿主机只跑框架
- **中间件栈**：可扩展的 before/after/wrap 钩子
- **CompositeBackend**：路径路由到不同后端
- **MCP 协议**：统一工具调用接口
- **HITL**：interrupt/resume 实现人工审批
- **熔断器**：三态模型保护沙箱调用
- **sandbox_holder**：全局单例，工具通过 `get_sandbox()` 访问沙箱
- **评审回路**：grader 子 Agent 对照 rubric 打分，needs_revision 自动打回重做
- **可观测 trace**：阶段流转 + 评审判定持久化到 MongoDB

---

## 更新日志（2026-07-29 重大修复）

本次更新对 12 个关键文件进行了重大修复，以下是每个文件的变更摘要：

| 文件 | 旧版问题 | 新版方案 |
|------|----------|----------|
| `custom_opensandbox.py` | 类名 `DockerSandboxBackend`，仅 6 个方法 | `CustomOpenSandbox`，30+ 方法，多语言运行时 |
| `sandbox_setup.py` | 21 行，仅 `mkdir -p` | 413 行，7 层安全防护 + 多语言运行时 + 文件同步 |
| `sandbox_manager.py` | 83 行，只有 get/rebuild/destroy | 494 行，五态生命周期 + MongoDB 持久化 + 预热池 |
| `sandbox_proxy.py` | 18 个方法部分是空壳 | 18 个方法全部真实实现 |
| `sandbox_holder.py` | 不存在 | ★新增：全局沙箱持有器，工具通过 `get_sandbox()` 访问沙箱 |
| `context_injection.py` | 全局单例导致用户串扰 | 工厂模式，每次请求创建新实例 |
| `skills_sync.py` | 文件名哈希，丢失目录结构 | 相对路径 SHA256 哈希，保留完整目录，增量同步 |
| `user_skills_restore.py` | 6 个问题（空值/父目录/单例标记等） | 全部修复 + 增量同步 + error 日志 |
| `middleware_config.py` | 只返回 1 个 demo 中间件 | 返回完整中间件栈（5 个） |
| `download_sandbox_file.py` | 无法从沙箱下载文件 | 真实 Docker 文件提取（base64 传输） |
| `document_generator.py` | 不存在 | 新增：MD/HTML/CSV/JSON/TXT 文档生成（沙箱内输出） |
| `agent_loader.py` | `MemorySaver` + `InMemoryStore` | `MongoDBSaver` + `MongoDBStore` 生产级持久化 |
| `mongodb_store.py` | 不存在 | 新增：自定义 `BaseStore` 的 MongoDB 实现 |
| `chart_generator.py` | 宿主机 `subprocess` 执行 | ✅ 沙箱内 `sandbox.execute()` 执行 matplotlib |
| `web_fetch.py` | 直接解压到宿主机 | ✅ 沙箱隔离流程：下载→验证→通过→安装 |
| `main_agent.py` | `skills=["path"]` 报 `path_not_found` | ✅ `skills=None` + `_load_skills_prompt` 手动注入 |
| `main_agent.py` | 无项目文件同步 | ✅ `_upload_project_to_sandbox` 启动时上传 125+ 文件 |

---

## 更新日志（2026-08-26 Harness 架构真改造）

本次改造将 Harness 架构从"prompt 软约束 + 正则猜测"升级为"结构化状态 + 评审回路"，共 8 个提交。核心变化：

| 文件 | 旧版问题 | 新版方案 |
|------|----------|----------|
| `schema.py` | 无阶段/计划/评审模型 | ★新增 `Phase`/`PlanStep`/`Plan`/`ReviewResult` 强类型模型 |
| `harness.py` | 不存在 | ★新增：阶段状态机 + rubric 注入 + 任务类型识别 |
| `harness_config.yaml` | 不存在 | ★新增：声明式 DSL（四阶段/评审标准/任务类型） |
| `main_agent.py` | 阶段靠 prompt 软约束 | ★接入 `RubricMiddleware` 评审器 + `HarnessPhaseMiddleware` |
| `chat.py` | 阶段/todo 靠正则猜文本 | ★改从 values 流读 `state.phase`/`state.todos`，评审从 custom 流读 |
| `loader.py` | output_format 只声明不校验 | ★新增契约校验 + 输出契约注入子 Agent system_prompt |
| `prompts.py` | 文本规划格式 | ★改用 `write_todos` 工具 + 评审器自动审查 |
| `agent_loader.py` | 无可观测 trace | ★新增 `save_harness_trace` 持久化阶段流转 |

**架构转变核心**：

| 维度 | 旧版 | 新版 |
|------|------|------|
| Phase | 正则猜 LLM 文本 | `state.phase`（图状态，checkpoint 持久化） |
| Todo | 正则提编号列表 | `state.todos`（`TodoListMiddleware` 结构化） |
| Review | LLM 自述"审查" | `RubricMiddleware` grader 子 Agent 打分 + 打回回路 |
| output_format | 仅 YAML 声明 | 契约校验 + 注入 + 评审器校验 |
| 可观测 | 无 | `harness_traces` MongoDB 持久化 |

**阶段流转机制**：
```
before_agent  → phase=planning（注入 rubric）
after_model   → phase=executing（模型调用工具时）
after_agent   → phase=reviewing（needs_revision 打回重做）
              → phase=result（satisfied/failed/超限）
```
