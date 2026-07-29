# ERP 智能采购助手 — Harness Engineering 架构

> 基于 DeepAgent + LangGraph + MCP 协议的摩托车零部件采购智能助手，严格遵循 **Harness Engineering** 架构思想（Planning → Executing → Review → Result）。

---

## 项目简介

本项目是一个面向摩托车零部件采购管理场景的 **AI Agent 系统**。通过大语言模型（通义千问 qwen-plus）驱动的智能体，与已部署的 Java ERP 后端进行交互，实现：

- 供应商智能分析（信用评级、供货能力对比）
- 采购订单全生命周期管理（创建/修改/审批）
- 库存预警与出入库管理
- 零部件搜索与供应商关联查询
- 数据可视化图表生成（26 种图表类型）
- 结构化文档输出（Markdown/HTML/CSV/JSON）
- 人工审批流程（HITL — Human-in-the-Loop）

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **LLM** | 通义千问 qwen-plus | 阿里云 DashScope API |
| **Agent 框架** | DeepAgent + LangGraph | 状态图引擎，支持中断/恢复/子Agent |
| **MCP 协议** | FastMCP + SSE | Agent ↔ ERP 的工具桥接层 |
| **Web 框架** | FastAPI + Uvicorn | SSE 流式响应 |
| **前端** | Next.js 16 + React 19 + TailwindCSS 4 | 流式对话 UI + 中断交互 |
| **数据库** | MongoDB (Motor/Pymongo) | 会话/消息/Store 持久化 |
| **沙箱** | Docker SDK + 7 层安全防护 | 隔离代码执行环境 |
| **图表** | Matplotlib + Pandas | 26 种图表生成 |
| **语言** | Python 3.11+ / TypeScript | 后端 Python，前端 TypeScript |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js :3000)                       │
│              SSE 流式对话 + HITL 中断交互 + 历史管理              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│              Backend API (FastAPI :8000)                          │
│   chat.py (SSE流) + history.py (会话CRUD) + agent_loader.py      │
│   MongoDBStore + MongoDBSaver (生产级持久化)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              Agent Core (DeepAgent)                               │
│  ┌──────────┐ ┌───────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │ LLM      │ │ Composite     │ │ 9 中间件     │ │ 2 子Agent  │ │
│  │ qwen-plus│ │ Backend       │ │ (7自定义     │ │ analyst    │ │
│  │          │ │ (Docker+Store)│ │  +2框架内置) │ │ order      │ │
│  └──────────┘ └───────────────┘ └─────────────┘ └────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Tools: 23 MCP + 9 Custom = 32 个工具                         ││
│  │ chart(26种) + web_search + web_fetch + install_skill         ││
│  │ + hitl_tools + download_sandbox_file + document_generator    ││
│  └─────────────────────────────────────────────────────────────┘│
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP (SSE)
┌────────────────────────────▼────────────────────────────────────┐
│              MCP Server (FastMCP :9000)                           │
│   suppliers(5) + parts(5) + orders(7) + inventory(6) = 23 tools │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP REST
┌────────────────────────────▼────────────────────────────────────┐
│              Java ERP 后端 (:8081)                                │
│              http://47.92.108.163:8081                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心功能

### 1. Harness 工作流（Planning → Executing → Review → Result）
Agent 严格遵循四阶段工作流：
- **Planning**：分析用户意图，生成任务规划（前端展示 TodoList）
- **Executing**：调用 MCP 工具 / 沙箱执行代码 / 委派子Agent
- **Review**：审查执行结果，验证数据完整性
- **Result**：结构化输出最终结果

### 2. Docker 安全沙箱（7 层防护）
```
1. --read-only          文件系统只读
2. --tmpfs /tmp         临时目录内存挂载（限制大小）
3. --memory="512m"      内存上限
4. --cpus="1.0"         CPU 上限
5. --network bridge     网络隔离/受限
6. --cap-drop ALL       移除所有 Linux Capability
7. --security-opt       seccomp 系统调用白名单
```
支持可扩展多语言运行时：Python / Go / Node.js

### 3. 沙箱五态生命周期管理
```
预热池(WARM) → 认领(CLAIMED) → MongoDB缓存(CACHED)
     ↑                              │
     │ 补充预热                      │ 故障/超时
     │                              ↓
  新建(CREATE) ←────────────── 销毁(DESTROY)
```

### 4. HITL 人工审批
- 订单创建/更新触发 `interrupt_on` 中断
- 前端展示审批卡片，用户批准后恢复执行
- 缺少字段时触发信息补充中断

### 5. 子Agent 委派
- **procurement-analyst**：采购分析师（数据分析 + 图表生成）
- **procurement-order**：订单专家（订单 CRUD + 审批流程）

### 6. 9 层中间件栈
| # | 中间件 | 职责 |
|---|--------|------|
| 1 | SandboxHealthMiddleware | 沙箱健康检查 + 自动重连 |
| 2 | ContextInjectionMiddleware | 用户上下文注入（工厂模式隔离） |
| 3 | SkillsSyncMiddleware | 技能文件夹级增量同步 |
| 4 | UserSkillsRestoreMiddleware | 用户自定义技能恢复 |
| 5 | ToolsSummarizationMiddleware | 工具调用摘要监控 |
| 6 | MemoryUpdateMiddleware | 用户偏好自动提取 |
| 7 | SandboxCircuitBreakerMiddleware | 沙箱熔断器（三态模型） |
| 8 | ModelCallLimitMiddleware | 模型调用次数限制 |
| 9 | ToolCallLimitMiddleware | 工具调用次数限制 |

### 7. 32 个工具
- **23 个 MCP 工具**：供应商(5) + 零部件(5) + 订单(7) + 库存(6)
- **9 个自定义工具**：chart_generator, web_search, web_fetch, install_skill, request_order_info, download_sandbox_file, list_sandbox_files, generate_document, generate_table_report

---

## 项目结构

```
ERP-AGENT/
├── frontend/                          # Next.js 前端
│   ├── src/
│   │   ├── app/                       # App Router
│   │   ├── components/                # UI 组件
│   │   │   ├── chat/                  # 对话区（消息/输入/工具调用/思考动画）
│   │   │   ├── interrupt/             # HITL 中断交互（审批/补充信息）
│   │   │   ├── sidebar/              # 侧边栏（历史/搜索）
│   │   │   └── common/               # 通用组件
│   │   ├── hooks/                     # useChat / useSSE / useHistory
│   │   └── lib/                       # API / SSE解析 / 类型定义
│   └── package.json
│
├── src/                               # Python 后端
│   ├── agent/                         # Agent 核心
│   │   ├── main_agent.py              # 主入口：create_main_agent() 7步组装
│   │   ├── config.py                  # 全局配置
│   │   ├── middleware_config.py       # 子Agent中间件工厂
│   │   ├── backends/                  # Docker 沙箱后端
│   │   │   ├── custom_opensandbox.py  # Docker SDK 封装（30+ 方法）
│   │   │   ├── sandbox_setup.py       # 安全沙箱创建 + 多语言运行时
│   │   │   ├── sandbox_manager.py     # 五态生命周期管理
│   │   │   ├── sandbox_proxy.py       # 代理层（热替换）
│   │   │   └── seccomp.json           # seccomp 安全策略
│   │   ├── middlewares/               # 7 个自定义中间件
│   │   ├── tools/                     # 9 个自定义工具
│   │   │   ├── document_generator.py  # 文档生成（MD/HTML/CSV/JSON）
│   │   │   ├── download_sandbox_file.py # 沙箱文件下载
│   │   │   ├── chart_generator.py     # 26 种图表
│   │   │   ├── web_fetch.py           # URL抓取 + Skill安装
│   │   │   └── hitl_tools.py          # HITL 人工介入
│   │   ├── subagents/                 # 子Agent（YAML声明式）
│   │   └── memory/                    # 系统提示词 + 操作手册
│   ├── api_view/                      # FastAPI Web 层
│   │   ├── web_main.py                # 应用入口
│   │   ├── agent_loader.py            # Agent 单例（MongoDB持久化）
│   │   ├── mongodb_store.py           # LangGraph Store（MongoDB实现）
│   │   └── api/                       # 路由（chat + history）
│   ├── mcp_server/                    # MCP 网关（23个ERP工具）
│   ├── skills/                        # 技能文件（文件夹级）
│   └── download/                      # 生成文件下载目录
│
├── .env                               # 环境变量配置
├── requirements.txt                   # Python 依赖
└── PYTHON_BACKEND_GUIDE.md            # 后端代码完全解析（4000行）
```

---

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 18+
- MongoDB 6.0+
- Docker Desktop（已启动）
- 通义千问 API Key（DashScope）

### 1. 克隆项目 & 安装依赖

```bash
# 克隆项目
git clone <repo-url>
cd ERP-AGENT

# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd frontend
npm install
cd ..
```

### 2. 配置环境变量

编辑项目根目录 `.env` 文件：

```bash
# 通义千问 API Key（阿里云 DashScope）
DASHSCOPE_API_KEY=sk-your-api-key

# MongoDB 连接
MONGODB_URI=mongodb://localhost:27017

# Java ERP 后端地址
ERP_BASE_URL=http://47.92.108.163:8081

# MCP Server 地址（本地）
MCP_SERVER_URL=http://localhost:9000

# 沙箱 Docker 镜像
SANDBOX_IMAGE=python:3.11-slim
```

### 3. 启动 MongoDB

```bash
# 确保 MongoDB 正在运行
mongod --dbpath /path/to/data

# 或使用 Docker
docker run -d --name mongodb -p 27017:27017 mongo:6.0
```

### 4. 启动 Docker 沙箱容器

```bash
docker run -d \
  --name erp-sandbox \
  -w /workspace \
  python:3.11-slim \
  sleep infinity
```

### 5. 启动 MCP Server（端口 9000）

```bash
python -m src.mcp_server.server_main
```

看到以下输出表示成功：
```
🚀 Starting MCP Server on 0.0.0.0:9000 (SSE transport)
Uvicorn running on http://0.0.0.0:9000
```

### 6. 启动后端 API（端口 8000）

```bash
python -m src.api_view.web_main
```

看到以下输出表示成功：
```
AgentLoader initialized
Starting ERP Agent Web Server...
Uvicorn running on http://0.0.0.0:8000
```

### 7. 启动前端（端口 3000）

```bash
cd frontend
npm run dev
```

### 8. 访问应用

浏览器打开 http://localhost:3000 即可使用。

---

## 启动顺序总结

```
MongoDB → Docker沙箱 → MCP Server(:9000) → Backend API(:8000) → Frontend(:3000)
```

> 注意：MCP Server 必须在 Backend API 之前启动，因为 Agent 初始化时会连接 MCP Server 加载 23 个 ERP 工具。

---

## 项目亮点

### 1. 真正的 Harness Engineering 架构
不是简单的 ChatBot，而是严格遵循 **Planning → Executing → Review → Result** 四阶段工作流。前端实时展示每个阶段的状态变化（Phase Bar + TodoList），用户可清晰看到 Agent 的思考和执行过程。

### 2. 生产级 Docker 安全沙箱
7 层安全防护（只读文件系统 + tmpfs + 资源限制 + 网络隔离 + Capability 移除 + seccomp 白名单 + PID 限制），不是玩具级沙箱。支持多语言运行时扩展（Python/Go/Node.js），项目文件完整同步到沙箱实现真正隔离测试。

### 3. 五态沙箱生命周期
预热池 → 认领 → MongoDB 缓存 → 新建 → 销毁。服务重启不丢失用户绑定关系，预热池保证 < 100ms 分配速度，健康检查 + 自动重建故障容器。

### 4. 完整的 HITL 审批流程
订单创建/更新需人工审批，缺少字段时触发信息补充中断。基于 LangGraph 的 interrupt/resume 机制，前端展示审批卡片和信息补充表单。

### 5. 9 层中间件栈
沙箱健康检查、用户上下文注入（工厂模式防串扰）、技能增量同步、用户技能恢复、工具摘要监控、偏好自动提取、熔断器保护、调用限制。每个中间件都有明确的职责边界。

### 6. MCP 协议解耦
Agent 不直接调用 ERP API，而是通过 MCP Server 提供的 23 个标准化工具交互。MCP 层可独立部署、独立扩展，Agent 侧无需关心 ERP 接口细节。

### 7. MongoDB 全链路持久化
- **MongoDBSaver**：LangGraph Checkpointer（会话状态持久化）
- **MongoDBStore**：LangGraph Store（跨会话用户偏好/技能存储）
- **display_messages**：前端展示消息持久化
- **conversations**：会话列表管理

### 8. 子Agent 委派 + YAML 声明式配置
采购分析师和订单专家两个子Agent，通过 YAML 文件声明式配置（工具集、系统提示词、委派规则），主Agent 根据任务类型自动委派。

### 9. SSE 流式协议
完整的 SSE 事件协议：`thinking` → `token` → `tool_start` → `tool_result` → `phase` → `todo_update` → `interrupt` → `done`。前端逐 token 渲染，实时展示工具调用和阶段变化。

### 10. 技能系统（Skills）
文件夹级技能管理（SKILL.md + 脚本 + 依赖），支持安装/同步/恢复。SkillsSyncMiddleware 实现增量同步（SHA256 哈希比对），保留完整目录结构。

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | SSE 流式对话 |
| POST | `/api/chat/{thread_id}/resume` | 中断恢复 |
| GET | `/api/chat/{thread_id}/state` | 获取中断状态 |
| GET | `/api/chat/{thread_id}/history` | 获取消息历史 |
| GET | `/api/history/{user_id}` | 获取会话列表 |
| DELETE | `/api/history/{thread_id}` | 删除会话 |
| GET | `/api/download/{filename}` | 下载生成文件 |
| GET | `/health` | 健康检查 |

---

## 开发说明

- 后端代码详细解析见 [PYTHON_BACKEND_GUIDE.md](./PYTHON_BACKEND_GUIDE.md)（4000 行逐文件解析）
- 修改 Agent 行为：编辑 `src/agent/memory/prompts.py`（系统提示词）
- 添加新工具：在 `src/agent/tools/` 创建工具文件，在 `main_agent.py` 注册
- 添加新中间件：在 `src/agent/middlewares/` 创建，在 `main_agent.py` 中间件栈中添加
- 修改子Agent：编辑 `src/agent/subagents/configs/*.yaml`
