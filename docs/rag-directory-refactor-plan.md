# KnowledgeChat 目录重构方案

## 1. 目标

本方案只解决一件事：把 KnowledgeChat 后端代码按职责重新分层，避免继续把新能力堆进 `query` 或 `retrieval`。

重构目标：

- `query` 只负责问题理解与执行规划
- `executors` 负责组织不同业务链
- `retrieval` 只负责证据召回与排序
- `answering` 只负责回答、引用与拒答
- `text2sql` 独立承载结构化查询能力
- `evals` 独立承载评测与回放

---

## 2. 当前问题

当前目录的主要问题不是文件多，而是职责边界不够清楚：

- `query` 和 `retrieval` 的边界混杂
- `answer_assembler` 放在 `retrieval` 下，语义不准确
- 表格、公式、SQL 这类专用链路缺少统一的执行层
- 后续继续加能力时，容易出现“不知道放哪”的情况

---

## 3. 目标目录

建议目标目录如下：

```text
services/docs-core/src/docs_core/
  ingest/
    canonical/
    structured/
    storage/

  query/
    contracts.py
    intent_parser.py
    execution_planner.py
    service.py

  executors/
    __init__.py
    content_executor.py
    table_executor.py
    formula_executor.py
    sql_executor.py
    synthesis_executor.py

  retrieval/
    __init__.py
    query_normalizer.py
    sparse_retriever.py
    dense_retriever.py
    hybrid_retriever.py
    table_retriever.py
    formula_retriever.py
    reranker.py

  answering/
    __init__.py
    citation_builder.py
    answer_assembler.py
    refusal_policy.py

  text2sql/
    __init__.py
    schema_linker.py
    sql_planner.py
    sql_generator.py
    sql_validator.py
    sql_executor.py
    sql_explainer.py

  evals/
    __init__.py
    eval_retrieval.py
    eval_answer.py
    eval_text2sql.py
    eval_reporter.py
```

---

## 4. 分层规则

### `query`

只放：
- query contract
- intent parse
- execution planning
- query service 入口
不要放：
- 具体 retrieval 规则
- 回答拼装
- SQL 执行逻辑

### `executors`
只放：
- 各类问答链的编排逻辑
- 不同组件之间的组织调用

典型职责：
- `content_executor` 组织普通问答链
- `table_executor` 组织表格问答链
- `formula_executor` 组织公式/计算链
- `sql_executor` 组织 Text-to-SQL 链
- `synthesis_executor` 组织多证据综合链

### `retrieval`

只放：
- 检索器
- 召回融合
- rerank
- metadata filter

不要放：
- 意图识别
- 回答生成

### `answering`

只放：

- 回答拼装
- 引用构造
- 拒答策略

### `text2sql`

只放：

- schema link
- SQL planning
- SQL generation
- SQL validation
- SQL execution
- SQL explanation

---

## 5. 现有文件迁移建议

### 保持原位

- `ingest/canonical/*`
- `ingest/structured/*`
- `ingest/storage/*`
- `retrieval/query_normalizer.py`
- `retrieval/sparse_retriever.py`
- `retrieval/dense_retriever.py`
- `retrieval/hybrid_retriever.py`
- `retrieval/table_retriever.py`
- `retrieval/formula_retriever.py`
- `retrieval/reranker.py`

### 建议迁移

- `query/query_router.py`
  - 拆成 `query/intent_parser.py` 和 `query/execution_planner.py`
- `retrieval/citation_builder.py`
  - 移到 `answering/citation_builder.py`
- `retrieval/answer_assembler.py`
  - 移到 `answering/answer_assembler.py`
- `retrieval/service.py`
  - 逐步下沉为 executor 依赖，最终由 `executors/*` 接管主链编排
- `query/service.py`
  - 保留为统一入口，但内部改为调用 planner + executors

### 后续新增

- `executors/`
- `answering/`
- `text2sql/`
- `evals/`

---

## 6. 推荐迁移顺序

### Step 1

先新增目录：
- 新增 `executors/`
- 新增 `answering/`

迁移回答层，把“召回”和“回答”分开：
- `citation_builder.py`
- `answer_assembler.py`

拆分 query，`query` 只保留理解与规划：
- `query_router.py -> intent_parser.py + execution_planner.py`


引入执行层，不再由单个 service 同时承担所有链路编排：
- 新增 `content_executor.py`
- 新增 `table_executor.py`
- 新增 `formula_executor.py`




### Step 2

补齐 `text2sql/` 与 `evals/`
目标：
- 为统计问答和评测服务化留出稳定边界
- 新增 `text2sql/__init__.py`
- 新增 `schema_linker.py`
- 新增 `sql_planner.py`
- 新增 `sql_generator.py`
- 新增 `sql_validator.py`
- 新增 `sql_executor.py`
- 新增 `sql_explainer.py`
- 新增 `executors/sql_executor.py`
- 让 `analytic_sql` 正式走 `planner -> sql executor -> text2sql/*`
- 新增 `evals/__init__.py`
- 新增 `eval_retrieval.py`
- 新增 `eval_answer.py`
- 新增 `eval_text2sql.py`
- 新增 `eval_reporter.py`
- 现有 `tests/evals/knowledge_rag/*` 保留数据与薄入口，评测逻辑下沉到 `docs_core/evals/*`

完成标准：
- `retrieval` 仍只负责召回
- `query` 不直接写 SQL
- `executors/sql_executor.py` 负责组织最小 Text-to-SQL 链
- `text2sql/*` 负责 schema link / planning / generation / validation / execution / explanation
- `evals/*` 负责 retrieval / answer / text2sql 三类评测与统一报告
- `/api/knowledge/query` 在 `analytic_sql` 场景下返回 `sql` payload，且契约不变

---

## 7. 实施原则

- 先收职责边界，再新增能力
- 先迁移调用关系，再迁移文件名
- 做完兼容式重构且自主测试完成后，删除老旧代码、命名和文件
- 每一步都保证 `/api/knowledge/query` 契约不变

---

## 8. 最小落地版本

如果只做最小必要重构，建议先完成以下四件事：
1. 新增 `answering/`
2. 把 `citation_builder.py` 和 `answer_assembler.py` 移过去
3. 把 `query_router.py` 拆成 `intent_parser.py` 与 `execution_planner.py`
4. 新增 `executors/`，先落 `content_executor.py`、`table_executor.py`、`formula_executor.py`
如果继续做到 Step 2，则再补两件事：
5. 新增 `text2sql/`，让 `analytic_sql` 不再是占位返回
6. 新增 `evals/`，把 retrieval / answer / text2sql 评测逻辑下沉到服务内
做到这一步后，目录结构就会明显清晰，统计问答与评测服务化边界也已经明确。

---

## 9. 一句话结论
这次目录重构的核心，不是“把文件挪一挪”，而是把系统明确成：
`Query 负责理解，Executors 负责编排，Retrieval 负责召回，Answering 负责作答。`
