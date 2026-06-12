# CLAUDE.md — SuperBizAgent 项目指引

## 项目概览

**SuperBizAgent** (v1.3.0) 是一套企业级智能 OnCall 运维系统，基于 FastAPI + LangChain + LangGraph 构建，提供 RAG 知识库问答（含 BM25+向量混合检索）和 AIOps 智能故障诊断能力，并内置可插拔的 Skill 领域知识包系统。

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
│   │   ├── health.py             # 健康检查（含 Milvus 状态）
│   │   └── skills.py             # Skill 热加载/卸载/查询接口
│   ├── services/                 # 业务服务层
│   │   ├── rag_agent_service.py  # RAG Agent (LangGraph + ChatQwen 原生集成)
│   │   ├── aiops_service.py      # Plan-Execute-Replan 工作流编排
│   │   ├── vector_store_manager.py    # LangChain Milvus VectorStore 封装
│   │   ├── vector_embedding_service.py # DashScope Embeddings (OpenAI 兼容)
│   │   ├── vector_index_service.py    # 文档批量索引
│   │   ├── vector_search_service.py   # 底层向量搜索（直接操作 pymilvus）
│   │   ├── document_splitter_service.py # Markdown/文本智能分割
│   │   ├── bm25_index_service.py  # BM25 关键词索引（jieba 分词 + BM25Okapi）
│   │   └── hybrid_retriever_service.py # 混合检索（BM25+向量双路召回 + RRF 融合）
│   ├── skills/                   # Skill 领域知识包系统
│   │   ├── __init__.py           # 模块导出
│   │   ├── base.py               # SkillManifest / SkillContext 数据模型
│   │   ├── registry.py           # SkillRegistry — Skill 发现与注册
│   │   ├── manager.py            # SkillManager — 激活/匹配/索引/上下文聚合
│   │   └── builtin/              # 内置 Skill（5 个运维领域）
│   │       ├── cpu_troubleshoot/     # CPU 故障排查（prompt.md + tools.py + docs/）
│   │       ├── memory_troubleshoot/  # 内存故障排查
│   │       ├── disk_troubleshoot/    # 磁盘故障排查
│   │       ├── service_unavailable/  # 服务不可用排查
│   │       └── slow_response/        # 响应慢排查
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
│   │   ├── knowledge_tool.py     # 知识库检索（支持混合检索 + content_and_artifact）
│   │   ├── time_tool.py          # 当前时间查询
│   │   └── query_metrics_alerts.py # Prometheus 告警查询 (GET /api/v1/alerts)
│   ├── core/                     # 基础设施
│   │   ├── llm_factory.py        # ChatOpenAI 兼容工厂（备用，实际多用 ChatQwen）
│   │   └── milvus_client.py      # Milvus 连接管理（单例 + ORM 别名 patch）
│   └── utils/
│       └── logger.py             # Loguru 配置（控制台 + 按天轮转文件）
├── eval/                         # 检索质量评估框架
│   ├── queries.py                # 15 条测试查询（5 领域 × 3 查询）
│   ├── ground_truth.py           # 基于 metadata.skill 自动标注 ground truth
│   ├── metrics.py                # Recall@K / MRR / NDCG@K 指标函数
│   ├── evaluator.py              # RetrievalEvaluator 三路对比（Vector/BM25/Hybrid）
│   └── run_evaluation.py         # 评估入口脚本
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
│  services/  ← 业务逻辑编排（RAG / AIOps / 检索） │
├──────────────────────────────────────────────────┤
│  skills/  ← Skill 领域知识包（按需激活/工具注入） │
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

## 三大核心功能流

### 1. RAG 对话 (chat.py → rag_agent_service.py)

```
User Question
  → chat.py 路由
  → RagAgentService.query() / query_stream()
  → SkillManager.match(question) → 激活匹配的 Skill（注入领域 tools + prompt）
  → _initialize_agent(): 加载本地 tools + Skill tools + MCP tools
  → create_agent(model, tools, checkpointer) → LangGraph Agent
  → [Model 决策] → 调用知识库检索 (hybrid: BM25+Vector+RRF) / MCP 工具
  → 返回最终答案（普通/SSE 流式）
```

- 使用 `langchain_qwq.ChatQwen` 原生集成（非 ChatOpenAI 兼容模式）
- 工具集 = `DEFAULT_LOCAL_AGENT_TOOLS` (retrieve_knowledge, get_current_time, query_prometheus_alerts) + 激活 Skill 的专用 tools + MCP tools
- **知识库检索**: 默认使用混合检索（BM25 + 向量双路召回 + RRF 融合），可通过 `HYBRID_ENABLED=False` 降级为纯向量检索
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

### 3. Skill 领域知识包系统 (skills/ + api/skills.py)

```
Skill 目录结构 (每个 Skill 一个子目录):
  builtin/{skill_name}/
    ├── prompt.md       # 专业系统提示词（注入 Agent system message）
    ├── tools.py        # 专用工具函数（@tool 装饰器，自动注册）
    └── docs/*.md       # 领域知识文档（启动时自动索引到 Milvus）

启动流程 (app/main.py lifespan):
  → skill_manager.discover_all()    # 扫描 builtin/ 下所有 Skill 目录
  → skill_manager.activate_all()    # 激活全部 Skill（可通过配置控制）
  → skill_manager.index_all_skills() # 将 Skill 知识文档索引到 Milvus

运行时匹配 (rag_agent_service.py):
  → skill_manager.match(question)   # 关键词匹配（基于 Skill keywords 字段）
  → skill_manager.activate(name)    # 按需激活匹配的 Skill
  → skill_manager.get_active_context_for_agent()  # 获取当前激活 Skill 的 tools + prompt
  → 注入到 LangGraph Agent 的 system message 和 tools 列表
```

**Skill 组成要素**:
- **Manifest** (`base.SkillManifest`): name, display_name, description, version, keywords（匹配用）, tags, enabled
- **Context** (`base.SkillContext`): 激活后聚合的 tools + system_prompt + knowledge_docs
- **Registry** (`registry.SkillRegistry`): 全局注册表，管理 Skill 生命周期（discover/activate/deactivate/index/get）
- **Manager** (`manager.SkillManager`): 业务编排层，关键词匹配 + 聚合激活 Skill 的上下文

**匹配策略**: 关键词匹配（`config.skill_match_top_k` 控制每轮最多激活数）
- 用户问题与每个 Skill 的 `keywords` 列表做子串匹配
- 按匹配数降序，取 top_k 个激活
- `skill_auto_activate` 控制 RAG Agent 是否自动匹配

**热加载**: 通过 API 接口支持运行时加载/卸载 Skill，无需重启服务
- `POST /api/skills/{name}/activate` — 激活 Skill
- `POST /api/skills/{name}/deactivate` — 停用 Skill
- `POST /api/skills/reload` — 重新扫描 Skill 目录
- `GET /api/skills` — 列出所有 Skill 状态
- `POST /api/skills/{name}/index` — 手动索引 Skill 知识文档

---

## 关键依赖

| 类别 | 包 | 用途 |
|------|-----|------|
| Web 框架 | fastapi, uvicorn, sse-starlette | API 服务 + SSE 流式 |
| LLM | langchain, langchain-core, langchain-qwq, dashscope, openai | Agent + 模型调用 |
| 工作流 | langgraph | StateGraph (RAG Agent + AIOps) |
| 向量库 | pymilvus, langchain-milvus | 文档存储和检索 |
| 文档处理 | langchain-text-splitters | Markdown/文本分割 |
| 检索增强 | rank-bm25, jieba | BM25 关键词检索 + 中文分词 |
| MCP | fastmcp, langchain-mcp-adapters, mcp | 工具协议集成 |
| 工具 | httpx, aiohttp, aiofiles | HTTP 客户端 + 异步文件 |
| 监控 | prometheus-fastapi-instrumentator | Prometheus /metrics 端点 |
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
| `HYBRID_ENABLED` | True | 混合检索主开关（False=纯向量降级） |
| `HYBRID_BM25_TOP_K` | 10 | BM25 路候选数 |
| `HYBRID_VECTOR_TOP_K` | 10 | 向量路候选数 |
| `HYBRID_RRF_K` | 60 | RRF 融合平滑常数 |
| `HYBRID_FINAL_TOP_K` | 5 | RRF 融合后最终返回数 |
| `SKILL_DIR` | ./app/skills/builtin | Skill 目录路径 |
| `SKILL_AUTO_INDEX` | True | 启动时自动索引 Skill 文档 |
| `SKILL_AUTO_ACTIVATE` | True | RAG 对话自动匹配激活 Skill |
| `SKILL_MATCH_TOP_K` | 2 | 每次最多激活 Skill 数 |
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
- `vector_store_manager` (VectorStoreManager) — 延迟初始化，首次调用时连接
- `bm25_index_service` (BM25IndexService) — 延迟初始化，首次 search() 时构建索引
- `hybrid_retriever_service` (HybridRetrieverService)
- `skill_manager` (SkillManager) — Skill 生命周期管理
- `skill_registry` (SkillRegistry) — Skill 注册表
- `vector_embedding_service` (DashScopeEmbeddings)
- `vector_index_service` (VectorIndexService)
- `vector_search_service` (VectorSearchService)
- `document_splitter_service` (DocumentSplitterService)
- `_mcp_client` (MultiServerMCPClient, 延迟初始化)

### 工具函数约定

- 使用 `@tool` 装饰器（langchain_core.tools）
- `retrieve_knowledge` 使用 `response_format="content_and_artifact"` 同时返回格式文本和原始文档
- `retrieve_knowledge` 内部集成了混合检索（BM25+向量+RRF），由 `HYBRID_ENABLED` 配置控制
- Skill 专用工具定义在各 `builtin/{skill}/tools.py` 中，由 SkillManager 统一注入
- 工具通过 `DEFAULT_LOCAL_AGENT_TOOLS` 元组 + Skill 注入工具统一注册

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

### Git 工作流约定 🔴 重要

- **每次 PR 使用新分支**: 远程分支在 PR merge 后会被立即删除（个人项目，保持 git 历史整洁）
- 分支命名: `feat/<feature-name>` / `fix/<bug-name>` / `docs/<what>` / `refactor/<what>`
- 绝对不要在已有分支上继续提交新的 PR——旧分支可能已被远程删除，force push 会丢失 commits
- 提交信息末尾统一附加 `Co-Authored-By: Claude <noreply@anthropic.com>`

### 文档同步约定 🔴 重要

**每次代码变更后必须同步更新以下配套文档**，保持文档与代码一致：

| 文档 | 触发条件 | 更新内容 |
|------|----------|----------|
| **CLAUDE.md** | 任何架构/模块/配置变更 | 目录结构、架构分层、功能流、依赖表、配置表、单例列表、开发约定 |
| **README.md** | 面向用户的功能变更 | 核心特性、技术栈、API 表、项目结构、配置说明、功能章节 |

**检查清单**（提交代码前逐项确认）：
1. 新增/删除文件 → 更新两个文档的目录结构图
2. 新增/修改配置项 → 更新两个文档的配置表
3. 新增功能模块 → README 加功能章节，CLAUDE.md 加功能流说明
4. 新增依赖包 → 更新两个文档的依赖/技术栈表
5. 新增全局单例 → 更新 CLAUDE.md 单例列表
6. 架构层级变化 → 更新 CLAUDE.md 架构分层图
7. API 端点变更 → 更新 README.md API 接口表
8. 版本号 → CLAUDE.md 项目概览中的版本号

**原因**: CLAUDE.md 是每次 AI 会话自动加载的上下文，过时会导致 AI 基于错误架构做决策。README.md 是项目门面，过时会误导新开发者。

### 流式输出模式

- RAG 对话：`stream_mode="messages"`，逐 token 输出
- AIOps 诊断：`stream_mode="updates"`，按节点状态输出
- 前端通过 SSE `EventSourceResponse` 接收事件（使用 sse-starlette）

### 混合检索 (BM25 + Vector + RRF)

```
检索流程 (hybrid_retriever_service.py):
  query → BM25 关键词检索 (jieba 分词 + BM25Okapi, top_k=10)
       → 向量相似度检索 (Milvus L2, top_k=10)
       → RRF 融合: score(doc) = Σ 1/(k + rank_i), k=60
       → 返回 top_k=5 融合结果
```

- **BM25 索引** (`bm25_index_service.py`): 延迟初始化，首次 search() 时从 Milvus 加载全部文档构建 BM25Okapi 索引
- **降级策略**: BM25 构建失败或 `hybrid_enabled=False` 时自动降级为纯向量检索
- **文档去重**: 基于 `_file_name + hash(content_prefix)` 作为 RRF 融合的文档 key
- **评估框架** (`eval/`): 支持 Vector/BM25/Hybrid 三路对比，指标含 Recall@K, MRR, NDCG@K
- **运行评估**: `python eval/run_evaluation.py`（需先启动 Milvus 并完成文档索引）
