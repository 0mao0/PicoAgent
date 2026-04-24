# Knowledge RAG Eval Templates

本目录用于存放 KnowledgeChat RAG 的离线评测样本。

## 文件说明

- `eval_1.json`
  - 单文件题库包；每道题聚合 `question`、`retrieval`、`answer`、`sql` 等字段。
  - 顶层 `dataset` 保存题库元信息，如 `dataset_id`、`title`、`schema_version`、`version`。
  - 顶层 `items` 为题目数组，每个 item 的最小字段为 `question_id`、`question`、`library_id`。
  - 后续可在单题下继续扩展 `reasoning`、`thought_process`、`grading_rules`、`source_notes`、`exam_year` 等字段。
- `eval_retrieval.py`
  - 调用当前知识检索主链并计算 Recall@3、Recall@5、MRR，并额外统计拒答样本的空检索正确率。
- `eval_answer.py`
  - 调用当前知识检索主链并评估回答非空率、必须引用命中率、拒答正确率。
- `eval_text2sql.py`
  - 调用当前 Text-to-SQL 主链并评估 SQL 执行成功率与精确匹配率。

## 使用原则

- `eval_1.json` 是当前唯一真相源。
- 每道题一条 `item`，`question_id` 在同一题库内必须唯一。
- 没有对应 SQL 的问题，可以省略 `sql` 字段。
- 优先使用真实文档问题，覆盖命中、表格、定位和拒答等不同场景。
- 多题库可直接并存于本目录，例如 `eval_1.json`、`exam_2024.json`、`exam_2025.json`；系统会自动合并读取。
- 对于拒答样本，建议在 `answer.refusal_expected` 中显式标注。
- 对于检索评测，优先使用 `retrieval.gold_section_paths` 作为稳定命中范围，避免绑定易变的内部 `chunk_id`。
- 对于重叠条文场景，可在同一题下给出多个可接受章节路径、评分规则或答案检查条件。

## 运行方式

- 检索评测：
  - `python tests/evals/knowledge_rag/eval_retrieval.py`
- 回答评测：
  - `python tests/evals/knowledge_rag/eval_answer.py`
- Text-to-SQL 评测：
  - `python tests/evals/knowledge_rag/eval_text2sql.py`
- 一键运行：
  - `pnpm run eval:knowledge-rag`
