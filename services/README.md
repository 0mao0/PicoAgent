# services/

AnGIneer 后端服务与核心库目录。

## 模块索引

### API 服务（FastAPI 后端，可独立部署）

| 模块 | 端口 | 说明 |
|------|------|------|
| [aichat-api](./aichat-api/) | 8791 | AI 问答服务：Agent 多轮会话（SSE）、模型配置、SOP、Evals 与 Dream Cycle |
| [docs-api](./docs-api/) | 8790 | 文档处理服务：文档解析、知识库、图谱、产物下载与 API Key 管理 |

### 核心库（Python 包，被 API 调用）

| 模块 | 说明 |
|------|------|
| [angineer-core](./angineer-core/) | 核心模块：Agent 循环、会话管理、工具调度、策略、检索、QA 管线、SOP 运行 |
| [docs-core](./docs-core/) | 文档解析引擎：基于 MinerU 的高保真 PDF 解析、语义检索、公式计算、块级溯源 |
| [evals-core](./evals-core/) | 评测引擎：夜间评测、异常补判、门禁检查、结论生成 |
| [ai-inference](./ai-inference/) | AI 推理客户端库：LLM 多模型路由、调用、可靠性、解析（[PyPI](https://pypi.org/project/angineer-ai-inference/)） |
| [engtools](./engtools/) | 工程工具集：表格、计算器、知识库查询、条件判断、用户输入等工具 |
| [geo-core](./geo-core/) | 地理引擎：GIS 空间分析与数据处理 |
| [sop-core](./sop-core/) | SOP 引擎：标准作业程序解析、加载、验证、路径生成 |
| [tree-core](./tree-core/) | 树操作基础设施：层级数据存储与契约定义 |
| [shared](./shared/) | 跨服务共享工具：配置验证等通用 utilities |

## 依赖关系

```
aichat-api ──┬──> angineer-core
             ├──> evals-core
             ├──> sop-core
             ├──> ai-inference
             └──> shared

docs-api ────┬──> docs-core
             └──> shared
```

## 开发规范

- **API 服务**：使用 FastAPI，端口配置在 `apps/shared/ports.json`
- **核心库**：纯 Python 包，不含 HTTP 服务，通过 `pyproject.toml` 定义依赖
- **共享代码**：跨服务复用的工具函数放 `shared/`，避免循环依赖
