# SuperBizAgent

> 企业级智能对话和运维助手，支持 RAG 知识库问答和 AIOps 智能诊断

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-latest-orange.svg)](https://www.langchain.com/)

## ✨ 核心特性

- 🤖 **智能对话** - LangChain 多轮对话 + 流式输出
- 📚 **RAG 问答** — BM25 + 向量混合检索 + RRF 融合，支持 TXT/MD/PDF/DOCX/HTML/CSV/XLSX 多格式文档上传和自动索引，内含错误修复机制
- 🧩 **Skill 系统** - 可插拔领域知识包，关键词自动匹配，热加载无需重启
- 🔧 **AIOps 诊断** - Plan-Execute-Replan 自动故障诊断和根因分析
- 🌐 **Web 界面** - 现代化 UI，支持多种对话模式：快速问答/流式对话
- 🔌 **MCP 集成** - 日志查询和监控数据工具接入

## 🛠️ 技术栈

- **框架**: FastAPI + LangChain + LangGraph
- **LLM**: 阿里云 DashScope (通义千问)
- **向量库**: Milvus
- **检索增强**: BM25 (rank-bm25) + jieba 中文分词 + RRF 融合
- **文档解析**: pymupdf (PDF), pypdf (PDF回退), docx2txt (DOCX), python-docx (DOCX回退), BS4 (HTML), openpyxl (XLSX) — 全部可选依赖
- **工具协议**: MCP (Model Context Protocol)

## 🚀 快速开始

### 环境要求

- Python 3.11+
- 阿里云 DashScope API Key ([获取地址](https://dashscope.aliyun.com/))

### 安装和启动

#### Linux/macOS 环境

```bash
# 1. 克隆项目
git clone <repository_url>
cd super_biz_agent_py

# 2. 安装依赖（推荐使用 uv）
# 方式 1: 使用 uv（推荐，更快）
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e .

# 方式 2: 使用 pip
pip install -e .

# 3. 编辑配置文件
# 首次使用需要编辑 .env 文件，填入你的 DASHSCOPE_API_KEY
vim .env  # 或使用其他编辑器

# 4. 一键初始化（启动 Docker + 服务 + 上传文档）
make init

# 5. 一键启动
make start
```

#### Windows 环境（PowerShell/CMD）

如果Windows 不支持 `make` 命令，可以手动执行以下步骤以启动服务：

```powershell
# 1. 克隆项目
git clone <repository_url>
cd super_biz_agent_py

# 2. 创建虚拟环境并安装依赖
# 方式 1: 使用 uv（推荐，更快）
pip install uv
# 创建虚拟环境
uv venv
# 激活虚拟环境
.venv\Scripts\activate
# 安装所有依赖
uv pip install -e .

# 方式 2: 使用 pip
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# 3. 编辑配置文件
# 使用记事本或其他编辑器打开 .env 文件，填入你的 DASHSCOPE_API_KEY
notepad .env

# 4. 启动 Docker Desktop
# 确保 Docker Desktop 已安装并正在运行

# 5. 启动 Milvus 向量数据库（Docker Compose）
docker compose -f vector-database.yml up -d

# 6. 等待 Milvus 启动完成（约 5-10 秒）
timeout /t 10

# 7. 启动 MCP 服务
# 启动 CLS 日志查询服务（新开一个 PowerShell 窗口）
python mcp_servers/cls_server.py

# 启动 Monitor 监控服务（新开一个 PowerShell 窗口）
python mcp_servers/monitor_server.py

# 8. 启动 FastAPI 主服务（新开一个 PowerShell 窗口）
# 注意：日志会自动输出到 logs\app_YYYY-MM-DD.log
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900

# 9. 上传文档到向量库（新开一个 PowerShell 窗口）
# 等待服务启动完成后执行
timeout /t 5
python -c "import requests, os, time; [requests.post('http://localhost:9900/api/upload', files={'file': open(f'aiops-docs/{f}', 'rb')}) or time.sleep(1) for f in os.listdir('aiops-docs') if f.endswith('.md')]"
```

**Windows 一键启动脚本**（推荐）

使用启动脚本：

```powershell
# 启动所有服务
.\start-windows.bat

# 停止所有服务
.\stop-windows.bat
```

### 访问服务

- **Web 界面**: http://localhost:9900
- **API 文档**: http://localhost:9900/docs

## 📡 API 接口

### 核心接口

| 功能       | 方法   | 路径                        | 说明              |
| -------- | ---- | ------------------------- | --------------- |
| 普通对话     | POST | `/api/chat`               | 一次性返回           |
| 流式对话     | POST | `/api/chat_stream`        | SSE 流式输出        |
| AIOps 诊断 | POST | `/api/aiops`              | 自动故障诊断（流式）      |
| 文件上传     | POST | `/api/upload`             | 上传并索引文档         |
| Skill 列表  | GET  | `/api/skills`             | 列出所有 Skill 及状态  |
| Skill 激活  | POST | `/api/skills/{name}/activate`  | 按需激活 Skill      |
| Skill 停用  | POST | `/api/skills/{name}/deactivate`| 停用 Skill        |
| Skill 重载  | POST | `/api/skills/reload`      | 重新扫描 Skill 目录   |
| Skill 索引  | POST | `/api/skills/{name}/index`| 手动索引 Skill 知识文档 |
| 健康检查     | GET  | `/api/health`             | 服务状态检查          |

### 使用示例

```bash
# 普通对话
curl -X POST "http://localhost:9900/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-123","Question":"你好"}'

# 流式对话
curl -X POST "http://localhost:9900/api/chat_stream" \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-123","Question":"你好"}' \
  --no-buffer

# AIOps 诊断
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-123"}' \
  --no-buffer
```

## 📁 项目结构

```
OnCall_Agent/
├── app/                                    # 应用核心
│   ├── __init__.py                         # 包初始化（自动加载日志配置）
│   ├── main.py                             # FastAPI 应用入口（含 BM25/Skill 预热）
│   ├── config.py                           # 配置管理（含 Hybrid/Skill 配置）
│   ├── api/                                # API 路由层
│   │   ├── __init__.py
│   │   ├── chat.py                         # 对话接口（RAG 聊天 + Skill 匹配）
│   │   ├── aiops.py                        # AIOps 接口（故障诊断）
│   │   ├── file.py                         # 文件管理（文档上传）
│   │   ├── health.py                       # 健康检查（服务状态）
│   │   └── skills.py                       # Skill 管理接口（热加载/激活/停用）
│   ├── services/                           # 业务服务层
│   │   ├── __init__.py
│   │   ├── rag_agent_service.py            # RAG Agent（LangGraph + Skill 注入）
│   │   ├── aiops_service.py                # AIOps 服务（Plan-Execute-Replan）
│   │   ├── vector_store_manager.py         # 向量存储管理器
│   │   ├── vector_embedding_service.py     # 向量 Embedding 服务
│   │   ├── vector_index_service.py         # 向量索引服务
│   │   ├── vector_search_service.py        # 向量检索服务
│   │   ├── document_splitter_service.py    # 文档分割服务
│   │   ├── document_parser_service.py       # 文档解析（多格式文本提取+修复）
│   │   ├── bm25_index_service.py           # BM25 关键词索引（jieba 分词）
│   │   └── hybrid_retriever_service.py     # 混合检索（BM25+向量+RRF 融合）
│   ├── skills/                             # Skill 领域知识包系统
│   │   ├── __init__.py                     # 模块导出
│   │   ├── base.py                         # SkillManifest / SkillContext 模型
│   │   ├── registry.py                     # SkillRegistry — 注册与发现
│   │   ├── manager.py                      # SkillManager — 匹配/激活/索引
│   │   └── builtin/                        # 内置 Skill（5 个运维领域）
│   │       ├── cpu_troubleshoot/           # CPU 故障排查
│   │       ├── memory_troubleshoot/        # 内存故障排查
│   │       ├── disk_troubleshoot/          # 磁盘故障排查
│   │       ├── service_unavailable/        # 服务不可用排查
│   │       └── slow_response/              # 响应慢排查
│   ├── agent/                              # Agent 模块
│   │   ├── __init__.py
│   │   ├── mcp_client.py                   # MCP 客户端（单例 + 重试）
│   │   └── aiops/                          # AIOps 核心逻辑
│   │       ├── planner.py                  # Planner 节点
│   │       ├── executor.py                 # Executor 节点
│   │       ├── replanner.py                # Replanner 节点
│   │       ├── state.py                    # 状态定义
│   │       └── utils.py                    # 工具函数
│   ├── models/                             # 数据模型层
│   │   ├── aiops.py                        # AIOps 模型
│   │   ├── document.py                     # 文档模型
│   │   ├── request.py                      # 请求模型
│   │   └── response.py                     # 响应模型
│   ├── tools/                              # Agent 工具集
│   │   ├── knowledge_tool.py               # 知识库查询（混合检索 + 格式化）
│   │   ├── time_tool.py                    # 当前时间工具
│   │   └── query_metrics_alerts.py         # Prometheus 告警查询
│   ├── core/                               # 核心组件
│   │   ├── llm_factory.py                  # LLM 工厂（ChatOpenAI 兼容）
│   │   └── milvus_client.py                # Milvus 客户端
│   └── utils/
│       └── logger.py                       # Loguru 日志配置
├── eval/                                   # 检索质量评估框架
│   ├── queries.py                          # 15 条测试查询（5 领域 × 3）
│   ├── ground_truth.py                     # Ground truth 自动标注
│   ├── metrics.py                          # Recall@K / MRR / NDCG@K
│   ├── evaluator.py                        # 三路对比评估器
│   └── run_evaluation.py                   # 评估入口脚本
├── static/                                 # Web 前端（纯静态）
│   ├── index.html                          # 主页面
│   ├── app.js                              # 前端逻辑
│   └── styles.css                          # 样式表
├── mcp_servers/                            # MCP 服务器
│   ├── cls_server.py                       # CLS 日志查询（Mock，端口 8003）
│   └── monitor_server.py                   # 监控数据（Mock，端口 8004）
├── aiops-docs/                             # 运维知识库（Markdown）
├── logs/                                   # 日志目录（Loguru 按天轮转）
├── .env                                    # 环境变量配置
├── Makefile                                # Linux/macOS 项目管理
├── start-windows.bat / stop-windows.bat    # Windows 启停脚本
├── vector-database.yml                     # Milvus Docker Compose
├── pyproject.toml                          # 项目元数据 + 依赖配置
└── README.md                               # 项目说明
```

## ⚙️ 配置说明

通过 `.env` 文件配置：

```bash
# 阿里云LLM DashScope 配置（必填）
# 秘钥管理： https://bailian.console.aliyun.com/
DASHSCOPE_API_KEY=your-api-key
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-max
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4

# Milvus 配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# RAG 配置
RAG_TOP_K=3
CHUNK_MAX_SIZE=800
CHUNK_OVERLAP=100

# 混合检索 (BM25 + 向量 + RRF)
HYBRID_ENABLED=True          # 主开关：False 降级为纯向量检索
HYBRID_BM25_TOP_K=10         # BM25 路候选数
HYBRID_VECTOR_TOP_K=10       # 向量路候选数
HYBRID_RRF_K=60              # RRF 平滑常数
HYBRID_FINAL_TOP_K=5         # 融合后返回数

# Skill 领域知识包
SKILL_DIR=./app/skills/builtin
SKILL_AUTO_INDEX=True        # 启动时自动索引 Skill 文档
SKILL_AUTO_ACTIVATE=True     # 对话时自动匹配激活
SKILL_MATCH_TOP_K=2          # 每次最多激活 Skill 数

# MCP 服务
MCP_CLS_URL=http://localhost:8003/mcp
MCP_MONITOR_URL=http://localhost:8004/mcp

# Prometheus
PROMETHEUS_BASE_URL=http://127.0.0.1:9090
```

## 🎯 AIOps 智能运维

基于 **Plan-Execute-Replan** 模式实现自动故障诊断。

### 核心特性

- ✅ 自动制定诊断计划（Planner）
- ✅ 智能工具调用（Executor）
- ✅ 动态调整步骤（Replanner）
- ✅ 流式输出诊断过程
- ✅ 生成结构化报告

### 快速测试

```bash
# 服务已通过 make init 自动启动
# 如需重启服务：make restart

# 访问 Web 界面，点击"智能运维与诊断工具"
# 或使用 API
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test"}' \
  --no-buffer
```

### 诊断流程

```
1. Planner 制定计划 → 生成 4-6 个诊断步骤
2. Executor 执行步骤 → 调用 MCP 工具（日志查询、监控数据）
3. Replanner 评估结果 → 决定继续/调整/生成报告
4. 输出诊断报告 → 根因分析 + 运维建议
```

## 🧩 Skill 领域知识包

每个 Skill 是一个独立的运维领域知识包，包含专业提示词、专用工具和知识文档，系统根据用户问题**自动匹配并激活**。

### 内置 Skill（5 个）

| Skill | 领域 | 匹配关键词示例 |
|-------|------|---------------|
| `cpu_troubleshoot` | CPU 故障排查 | CPU、使用率、飙升、死循环 |
| `memory_troubleshoot` | 内存故障排查 | 内存、OOM、堆内存、泄漏 |
| `disk_troubleshoot` | 磁盘故障排查 | 磁盘、空间不足、日志写满 |
| `service_unavailable` | 服务不可用 | 不可用、503、connection refused |
| `slow_response` | 响应慢排查 | 慢、延迟、P99、响应时间 |

### Skill 结构

```
builtin/{skill_name}/
├── prompt.md       # 专业系统提示词（注入 Agent）
├── tools.py        # 专用工具函数（@tool 装饰器）
└── docs/*.md       # 领域知识文档（自动索引到 Milvus）
```

### 管理 API

```bash
# 查看所有 Skill
curl http://localhost:9900/api/skills

# 激活指定 Skill
curl -X POST http://localhost:9900/api/skills/cpu_troubleshoot/activate

# 停用指定 Skill
curl -X POST http://localhost:9900/api/skills/cpu_troubleshoot/deactivate

# 重新扫描 Skill 目录（热加载）
curl -X POST http://localhost:9900/api/skills/reload
```

## 📊 检索评估

项目内置检索质量评估框架，支持 **Vector / BM25 / Hybrid (RRF)** 三路对比。

```bash
# 运行评估（需先启动 Milvus 并索引文档）
python eval/run_evaluation.py
```

评估指标：**Recall@K**（查全率）、**MRR**（首个正确结果排名）、**NDCG@K**（排名质量）。

## 📝 文档解析与修复

项目内置多格式文档解析器，支持 **8 种格式**，所有非标准库依赖均可选安装。

### 支持的格式

| 格式 | 安装命令 | 说明 |
|------|---------|------|
| TXT / MD | 内置 | 零依赖，自动编码检测 |
| PDF | `pip install -e ".[pdf]"` | pymupdf 主解析 + pypdf 回退 |
| DOCX | `pip install -e ".[docx]"` | docx2txt 主解析 + python-docx 回退 |
| HTML | `pip install -e ".[html]"` | bs4 + lxml 主解析 + html.parser 回退 |
| CSV | 内置 | Python 内置 csv 模块，含分隔符自动检测 |
| XLSX | `pip install -e ".[xlsx]"` | openpyxl read_only 流式模式 |

```bash
# 一键安装所有文档解析依赖
pip install -e ".[docs]"
```

### 错误修复机制

每个文件在主解析器失败时，自动尝试一次回退策略：
- 编码问题 → chardet 自动检测
- PDF 解析失败 → 自动切换 pypdf
- DOCX 解析失败 → 自动切换 python-docx
- HTML 解析失败 → 自动切换 Python 内置 html.parser
- CSV 解析失败 → 自动检测分隔符

修复成功对用户透明（仅记录日志），修复失败时返回详细的错误链（原始错误 + 尝试过的修复）。

## 📝 开发指南

### 常用命令

```bash
# 项目管理
make init              # 一键初始化（Docker + 服务 + 文档）
make start             # 启动所有服务
make stop              # 停止所有服务
make restart           # 重启所有服务

# 依赖管理
make install-dev       # 安装开发依赖
make sync              # 同步依赖

# Docker 管理
make up                # 启动 Docker 容器
make down              # 停止 Docker 容器

# 代码质量
make format            # 格式化代码
make lint              # 代码检查
```

## 🐛 常见问题

### Windows 环境问题

#### 1. `make` 命令不可用

Windows 不支持 `make` 命令，请使用提供的批处理脚本：

```powershell
# 启动服务
.\start-windows.bat

# 停止服务
.\stop-windows.bat
```

#### 2. PowerShell 执行策略限制

如果遇到 "无法加载文件，因为在此系统上禁止运行脚本" 错误：

```powershell
# 临时允许脚本执行（管理员权限）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 或者使用 CMD 而不是 PowerShell
cmd
.\start-windows.bat
```

#### 3. 端口被占用（Windows）

```powershell
# 查看占用端口的进程
netstat -ano | findstr :9900

# 结束进程（替换 PID 为实际进程 ID）
taskkill /F /PID <PID>
```

### 通用问题

### API Key 错误

```bash
# 检查环境变量
cat .env | grep DASHSCOPE_API_KEY    # Linux/macOS
type .env | findstr DASHSCOPE_API_KEY  # Windows
```

### Milvus 连接失败

```bash
# 确保本机有 Docker 服务并且已经启动（可以使用 Docker Desktop）

# 检查 Milvus 状态
docker ps | grep milvus

# 重启 Milvus（使用 docker compose）
docker compose -f vector-database.yml restart

# 或者重启单个服务
docker compose -f vector-database.yml restart standalone
```

### 服务无法启动

**Linux/macOS:**

```bash
# 查看服务日志
tail -f logs/app_$(date +%Y-%m-%d).log  # FastAPI 主服务（Loguru 日志）
tail -f mcp_cls.log                      # CLS MCP 服务
tail -f mcp_monitor.log                  # Monitor MCP 服务

# 检查端口占用
lsof -i :9900  # FastAPI
lsof -i :8003  # CLS MCP
lsof -i :8004  # Monitor MCP
```

**Windows:**

```powershell
# 查看服务日志（获取今天的日期）
$today = Get-Date -Format "yyyy-MM-dd"
type logs\app_$today.log  # FastAPI 主服务（Loguru 日志）
type mcp_cls.log          # CLS MCP 服务
type mcp_monitor.log      # Monitor MCP 服务

# 或者查看最新的日志文件
Get-ChildItem logs\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content -Tail 50

# 检查端口占用
netstat -ano | findstr :9900  # FastAPI
netstat -ano | findstr :8003  # CLS MCP
netstat -ano | findstr :8004  # Monitor MCP
```

## 📚 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangChain 文档](https://python.langchain.com/)
- [LangGraph Plan-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/)
- [阿里云 DashScope](https://dashscope.aliyun.com/)
- [MCP 协议](https://modelcontextprotocol.io/)

# 
