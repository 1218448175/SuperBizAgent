# CLAUDE.md — SuperBizAgent 项目指引

## 项目概览

**SuperBizAgent** (v1.2.1) 是一套企业级智能 OnCall 运维系统，基于 FastAPI + LangChain + LangGraph 构建，提供 RAG 知识库问答和 AIOps 智能故障诊断能力。

- **Python 版本**: >=3.11, <3.14 (`.python-version` 锁定 3.13)
- **包管理器**: uv (推荐) / pip
- **LLM**: 阿里云 DashScope (通义千问 qwen-max)，通过 OpenAI 兼容模式调用
- **向量库**: Milvus (Docker Compose 部署，collection 名 `biz`，维度 1024)
- **工具协议**: MCP (Model Context Protocol)，使用 `fastmcp` + `langchain-mcp-adapters`

---

## 目录结构

```
OnCall_Agent/
├── app/                          # 应用核心
│   ├── main.py                   # FastAPI 入口，lifespan 管理 Milvus 连接
│   ├── config.py                 # Pydantic Settings 配置（.env 驱动）
│   ├── api/                      # API 路由层
│   │   ├── chat.py               # 对话接口（普通/流式/会话管理）
│   │   ├── aiops.py              # AIOps 诊断接口（SSE 流式）
│   │   ├── file.py               # 文件上传 + 自动向量索引
│   │   └── health.py             # 健康检查（含 Milvus 状态）
│   ├── services/                 # 业务服务层
│   │   ├── rag_agent_service.py  # RAG Agent (LangGraph + ChatQwen 原生集成)
│   │   ├── aiops_service.py      # Plan-Execute-Replan 工作流编排
│   │   ├── vector_store_manager.py    # LangChain Milvus VectorStore 封装
│   │   ├── vector_embedding_service.py # DashScope Embeddings (OpenAI 兼容)
│   │   ├── vector_index_service.py    # 文档批量索引
│   │   ├── vector_search_service.py   # 底层向量搜索（直接操作 pymilvus）
│   │   └── document_splitter_service.py # Markdown/文本智能分割
│   ├── agent/                    # Agent 模块
│   │   ├── mcp_client.py         # MCP 全局客户端（单例 + 重试拦截器）
│   │   └── aiops/                # Plan-Execute-Replan 核心
│   │       ├── state.py          # PlanExecuteState TypedDict
│   │       ├── planner.py        # Planner 节点（含知识检索增强）
│   │       ├── executor.py       # Executor 节点（ToolNode 自动执行）
│   │       ├── replanner.py      # Replanner 节点（continue/replan/respond）
│   │       └── utils.py          # 工具描述格式化
│   ├── models/                   # Pydantic 数据模型
│   │   ├── request.py / response.py
│   │   ├── aiops.py              # AIOps 请求/响应/告警模型
│   │   └── document.py
│   ├── tools/                    # Agent 工具集（@tool 装饰器）
│   │   ├── knowledge_tool.py     # 知识库检索（content_and_artifact）
│   │   ├── time_tool.py          # 当前时间查询
│   │   └── query_metrics_alerts.py # Prometheus 告警查询 (GET /api/v1/alerts)
│   ├── core/                     # 基础设施
│   │   ├── llm_factory.py        # ChatOpenAI 兼容工厂（备用，实际多用 ChatQwen）
│   │   └── milvus_client.py      # Milvus 连接管理（单例 + ORM 别名 patch）
│   └── utils/
│       └── logger.py             # Loguru 配置（控制台 + 按天轮转文件）
├── mcp_servers/                  # MCP 服务（FastMCP，独立进程）
│   ├── cls_server.py             # CLS 日志查询（端口 8003，Mock 实现）
│   └── monitor_server.py         # 监控数据查询（端口 8004，Mock 实现）
├── static/                       # Web 前端（纯静态 HTML/JS/CSS）
├── aiops-docs/                   # 运维知识库（5 个 .md 文档）
├── .env                          # 环境变量配置
├── Makefile                      # Linux/macOS 项目管理
├── start-windows.bat / stop-windows.bat  # Windows 启停脚本
├── vector-database.yml           # Milvus Docker Compose
└── pyproject.toml                # 项目元数据 + 全部工具配置
```

---

## 架构分层

```
┌──────────────────────────────────────────────────┐
│  Static (HTML/JS/CSS)    │  API Consumers (curl) │
├──────────────────────────────────────────────────┤
│  api/  ← 路由层，薄层，只做参数提取和 SSE 转发   │
├──────────────────────────────────────────────────┤
│  services/  ← 业务逻辑编排（RAG Agent / AIOps）  │
├──────────────────────────────────────────────────┤
│  agent/  ← Agent 节点实现 + MCP 客户端管理       │
├──────────────────────────────────────────────────┤
│  tools/  ← @tool 函数，供 Agent 调用             │
├──────────────────────────────────────────────────┤
│  core/  ← 基础设施（LLM/Milvus 连接管理）        │
├──────────────────────────────────────────────────┤
│  models/  ← Pydantic 请求/响应模型               │
└──────────────────────────────────────────────────┘
```

## 两大核心功能流

### 1. RAG 对话 (chat.py → rag_agent_service.py)

```
User Question
  → chat.py 路由
  → RagAgentService.query() / query_stream()
  → _initialize_agent(): 加载本地 tools + MCP tools
  → create_agent(model, tools, checkpointer) → LangGraph Agent
  → [Model 决策] → 可能调用知识库检索 / MCP 工具
  → 返回最终答案（普通/SSE 流式）
```

- 使用 `langchain_qwq.ChatQwen` 原生集成（非 ChatOpenAI 兼容模式）
- 工具集 = `DEFAULT_LOCAL_AGENT_TOOLS` (retrieve_knowledge, get_current_time, query_prometheus_alerts) + MCP tools
- 会话持久化使用 `MemorySaver`（内存型，重启丢失）
- 流式输出通过 `stream_mode="messages"` 实现 token 级别流式

### 2. AIOps 诊断 (aiops.py → aiops_service.py → agent/aiops/*)

```
User Request (session_id)
  → aiops.py 路由
  → AIOpsService.diagnose()
  → 固定任务提示词注入
  → AIOpsService.execute() → LangGraph StateGraph
  → Planner → Executor → Replanner → (循环) → 最终报告
  → SSE 流式返回 (plan/step_complete/report/complete)
```

**Plan-Execute-Replan 工作流 (LangGraph StateGraph)**:
- **Planner**: 先检索知识库经验 → 获取全部工具列表 → ChatQwen 生成 Plan (步骤列表)
- **Executor**: 取第一个步骤 → LLM + ToolNode 自动工具调用 → 结果追加到 past_steps
- **Replanner**: 评估 → continue（不变）/ replan（替换剩余步骤）/ respond（生成最终报告）
  - 强制限制：最多 8 步，已执行 >= 5 步禁止 replan
  - 新步骤数不能超过当前剩余步骤数

---

## 关键依赖

| 类别 | 包 | 用途 |
|------|-----|------|
| Web 框架 | fastapi, uvicorn, sse-starlette | API 服务 + SSE 流式 |
| LLM | langchain, langchain-core, langchain-qwq, dashscope, openai | Agent + 模型调用 |
| 工作流 | langgraph | StateGraph (RAG Agent + AIOps) |
| 向量库 | pymilvus, langchain-milvus | 文档存储和检索 |
| 文档处理 | langchain-text-splitters | Markdown/文本分割 |
| MCP | fastmcp, langchain-mcp-adapters, mcp | 工具协议集成 |
| 工具 | httpx, aiohttp, aiofiles | HTTP 客户端 + 异步文件 |
| 日志 | loguru | 结构化日志 |
| 配置 | pydantic, pydantic-settings | 类型安全配置 |

---

## 启动方式

### 完整启动（3 个进程）

```bash
# 1. 启动 Milvus（Docker）
docker compose -f vector-database.yml up -d

# 2. 启动 MCP 服务（独立进程）
python mcp_servers/cls_server.py &      # 端口 8003
python mcp_servers/monitor_server.py &  # 端口 8004

# 3. 启动 FastAPI 主服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
# 或 make start / start-windows.bat
```

### MCP 服务说明

两个 MCP 服务器均为 **Mock 实现**，使用 `FastMCP` 框架：
- **CLS Server** (8003): 日志主题搜索、日志查询（返回模拟数据）
- **Monitor Server** (8004): CPU/内存监控指标查询（返回模拟趋势数据）

传输方式：`streamable-http`，路径 `/mcp`。可替换为腾讯云真实 MCP 端点。

---

## 配置项 (.env)

关键配置项（`app/config.py` 中 `Settings` 类定义）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHSCOPE_API_KEY` | (必填) | 阿里云 API Key |
| `DASHSCOPE_MODEL` | qwen-max | LLM 模型 |
| `DASHSCOPE_EMBEDDING_MODEL` | text-embedding-v4 | 嵌入模型 |
| `MILVUS_HOST/PORT` | localhost:19530 | 向量库地址 |
| `RAG_TOP_K` | 3 | 检索返回数 |
| `CHUNK_MAX_SIZE/OVERLAP` | 800/100 | 文档分割参数 |
| `MCP_CLS_URL` | http://localhost:8003/mcp | CLS MCP 地址 |
| `MCP_MONITOR_URL` | http://localhost:8004/mcp | Monitor MCP 地址 |
| `PROMETHEUS_BASE_URL` | http://127.0.0.1:9090 | Prometheus API 地址 |

---

## 开发约定

### 全局单例模式

项目大量使用模块级全局单例，在 import 时即初始化：
- `rag_agent_service` (RagAgentService)
- `aiops_service` (AIOpsService)
- `milvus_manager` (MilvusClientManager)
- `vector_store_manager` (VectorStoreManager)
- `vector_embedding_service` (DashScopeEmbeddings)
- `vector_index_service` (VectorIndexService)
- `vector_search_service` (VectorSearchService)
- `document_splitter_service` (DocumentSplitterService)
- `_mcp_client` (MultiServerMCPClient, 延迟初始化)

### 工具函数约定

- 使用 `@tool` 装饰器（langchain_core.tools）
- `retrieve_knowledge` 使用 `response_format="content_and_artifact"` 同时返回格式文本和原始文档
- 工具通过 `DEFAULT_LOCAL_AGENT_TOOLS` 元组统一注册

### LLM 调用约定

- RAG Agent 使用 `langchain_qwq.ChatQwen`（原生千问集成）
- AIOps Planner/Executor/Replanner 同样使用 `ChatQwen`，temperature=0（确定性输出）
- 备用方案：`LLMFactory.create_chat_model()` 使用 ChatOpenAI 兼容模式

### 代码质量

- 格式化：ruff + black，行宽 100
- Lint：ruff (E/W/F/I/C/B/UP 规则)
- 类型检查：mypy + pyright (basic 模式)
- 测试：pytest + pytest-asyncio (asyncio_mode=auto)，覆盖率目标 app/
- Pre-commit hooks 已配置

### 流式输出模式

- RAG 对话：`stream_mode="messages"`，逐 token 输出
- AIOps 诊断：`stream_mode="updates"`，按节点状态输出
- 前端通过 SSE `EventSourceResponse` 接收事件（使用 sse-starlette）
