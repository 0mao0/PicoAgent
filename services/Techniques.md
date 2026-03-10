# AnGIneer 后端技术实现细节

本文档描述文档解析与对比查改能力的后端改造方案，聚焦 API 网关、docs-core、engtools 三层联动。

---

## 后端常用命令（自动同步）

<!-- AUTO_SYNC:SERVICES_TECH_COMMANDS:START -->
```bash
pnpm install
pnpm dev:backend
pnpm harness
pnpm harness:workflow
pnpm harness:tooling
pnpm docs:sync
pnpm docs:check
```
<!-- AUTO_SYNC:SERVICES_TECH_COMMANDS:END -->

---

## 后端架构图（文档解析改造版）

```mermaid
flowchart TB
  subgraph Gateway["API 网关层 apps/api-server"]
    ParseAPI["/api/knowledge/parse\n异步任务提交"]
    TaskAPI["/api/knowledge/parse/tasks/{task_id}\n进度查询"]
    DocAPI["/api/knowledge/document/*\n原文/编辑版/版本"]
    StrategyAPI["/api/knowledge/strategies/*\nA/B/C 策略切换与查询"]
  end

  subgraph DocsCore["docs-core 知识引擎层"]
    KService["knowledge_service\n节点与任务状态"]
    Parser["mineru_parser\n高保真解析"]
    Storage["file_storage\n一文档一目录"]
    Struct["structured_indexer\n条文/表格/图片结构化"]
  end

  subgraph Strategy["检索执行平面"]
    A["A: 自研结构化检索\n(SQLite)"]
    B["B: MinerU-RAG 检索\n(外部向量能力)"]
    C["C: PageIndex 推理检索\n(树索引能力)"]
  end

  subgraph DB["数据与工件层"]
    Sqlite["data/knowledge.sqlite3\nnodes/tasks/artifacts/segments/revisions/eval_logs"]
    KB["data/knowledge_base/libraries/{library_id}/docs/{doc_id}\nsource/parsed/edited/structured"]
  end

  subgraph Tools["engtools 工具层"]
    KTool["KnowledgeTool\n优先结构化, 回退Markdown"]
    TTool["TableTool\n优先表格索引, 回退文本抽取"]
  end

  ParseAPI --> KService
  ParseAPI --> Parser
  Parser --> Storage
  Storage --> KB
  TaskAPI --> KService
  DocAPI --> Storage
  StrategyAPI --> A
  StrategyAPI --> B
  StrategyAPI --> C
  A --> Struct
  Struct --> Sqlite
  B --> Sqlite
  C --> Sqlite
  KService --> Sqlite
  KTool --> Sqlite
  TTool --> Sqlite
  KTool --> KB
  TTool --> KB
```

---

## PDF 对比高亮逻辑架构（后端）

```mermaid
flowchart TB
  subgraph Ingest["解析入口 apps/api-server/main.py"]
    ParseReq["POST /api/knowledge/parse\n提交解析任务"]
    ParseTask["_run_parse_task\n执行 MinerU 解析与落盘"]
  end

  subgraph Parser["解析核心 services/docs-core/parser/mineru_parser.py"]
    ParseMinerU["parse_document_with_mineru\n请求 MinerU 云端解析"]
    ExtractZip["_extract_zip_archive\n解压 cloud_result.zip"]
    BuildFinal["_build_final_result\n聚合 markdown + blocks + assets"]
    RecoverBlocks["ZIP 兜底恢复 blocks\n修复空 mineru_blocks.json"]
  end

  subgraph Storage["存储层 services/docs-core/storage/file_storage.py"]
    SaveMd["save_parsed_markdown\n写入 parsed/content.md"]
    SaveBlocks["save_mineru_blocks\n写入 parsed/mineru_blocks.json"]
    KeepAssets["保留 raw/cloud_result/images\n用于前端图片展示"]
  end

  subgraph ReadApi["读取入口 apps/api-server/main.py"]
    GetDoc["GET /api/knowledge/document/{library_id}/{doc_id}\n返回 content + storage + mineru_blocks"]
    GetStructured["GET /api/knowledge/document/{library_id}/{doc_id}/structured\n返回 structured_index.items"]
  end

  subgraph Contract["前端联动契约"]
    PageFields["页码字段\npage/page_no/page_idx"]
    RectFields["坐标字段\nbbox/rect/x0y0x1y1"]
    LineFields["行号字段\nline_start/line_end"]
  end

  ParseReq --> ParseTask
  ParseTask --> ParseMinerU
  ParseMinerU --> ExtractZip
  ExtractZip --> BuildFinal
  BuildFinal --> RecoverBlocks
  RecoverBlocks --> SaveMd
  RecoverBlocks --> SaveBlocks
  RecoverBlocks --> KeepAssets

  SaveMd --> GetDoc
  SaveBlocks --> GetDoc
  SaveBlocks --> GetStructured
  KeepAssets --> GetDoc

  GetDoc --> PageFields
  GetStructured --> PageFields
  GetDoc --> RectFields
  GetStructured --> RectFields
  GetDoc --> LineFields
  GetStructured --> LineFields
```

---

## 一文档一目录规范

```text
data/knowledge_base/libraries/{library_id}/docs/{doc_id}/
├─ source/
│  └─ {original_filename}
├─ parsed/
│  ├─ full.md
│  └─ assets/
├─ edited/
│  ├─ current.md
│  └─ revisions/{timestamp}.md
└─ structured/
   ├─ segments.json
   ├─ tables.json
   └─ images.json
```

---

## 可直接开工清单（后端文件级）

- `apps/api-server/main.py`
  - 解析接口改异步任务化，返回 `task_id`。
  - 增加任务进度查询、文档版本、策略切换与统一查询接口。
  - 三策略索引构建改为路由分发，实际实现下沉到 `docs_core.storage.*_strategy`。
- `services/docs-core/src/docs_core/storage/structured_strategy.py`
  - A 策略结构化索引提取与入库实现。
- `services/docs-core/src/docs_core/storage/mineru_rag_strategy.py`
  - B 策略（MinerU-RAG）索引构建与向量能力接入实现。
- `services/docs-core/src/docs_core/storage/pageindex_strategy.py`
  - C 策略（PageIndex）索引构建实现。
- `services/docs-core/src/docs_core/api/knowledge_api.py`
  - 扩展 `nodes` 字段，新增 `parse_tasks`、`document_artifacts`、`document_segments`、`document_tables`、`document_images`、`document_revisions`、`strategy_eval_logs` 表。
- `services/docs-core/src/docs_core/storage/file_storage.py`
  - 实现一文档一目录读写 API，保留旧路径兼容读取。
- `services/docs-core/src/docs_core/parser/mineru_parser.py`
  - 输出解析产物清单并支持阶段进度回调。
- `services/engtools/src/engtools/config.py`
  - 统一知识目录解析，支持新旧结构双栈。
- `services/engtools/src/engtools/KnowledgeTool.py`
  - 优先读取结构化片段，回退 Markdown 检索。
- `services/engtools/src/engtools/TableTool.py`
  - 优先读取结构化表格索引，回退 Markdown 表格解析。

---

## 三策略执行说明

- A（自研结构化）作为默认生产策略，检索路径最可控、可审计。
- B（MinerU-RAG）保留为对照策略，复用其检索能力并统一写评测日志。
- C（PageIndex）作为长文档推理检索增强策略，统一回传证据路径与耗时。
- 三策略统一写入 `strategy_eval_logs`，前端按文档与问题维度做横向比对。
