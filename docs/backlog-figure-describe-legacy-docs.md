# 待办：存量文档图描述补齐 与 83 篇产物重建

> 状态：**挂账，暂不动**（2026-09-06 与用户确认）。起因：VLM 图描述功能上线前的存量文档没有图简介索引，
> 且部分文档解析产物在 2026-09-06 误删事故中丢失（数据索引已从服务器快照完整救回，产物无法从快照恢复）。

## 现状盘点（2026-09-06 实测，本地与生产同构）

- 全库 283 篇 completed 文档，图描述（figure_describe 阶段，VLM=Qwen3 VL via dgx）覆盖 **176 篇**；
- 未做图描述 **107 篇**，分两类：

| 类别 | 篇数 | 缺什么 | 影响 |
|---|---|---|---|
| A. 解析产物在手（mineru_raw 存在） | **24** | 只差 VLM 图描述一步 | "图 N/第二张图"类问题答不出；图语义不可检索 |
| B. 产物双端丢失 | **83** | mineru/popo/render_pdf 产物目录 | 问答**不受影响**（正文+FTS+引用+向量四件套已从 9-05 快照回灌）；仅溯源面板 PDF 页面视图降级为 markdown、无图描述 |

清单文件：`data/recovery/doc_list.txt`（99 篇误删恢复清单，B 类主体在其中；`vectors_done.txt` 为向量回灌完成记录）。

## 方案

### 阶段 1（随时可做，无人工，约 1-2 小时 GPU）：A 类 24 篇补图描述
- 按文档触发 `POST /api/knowledge/documents/{doc_id}/stages/figure_describe/retry`
  （系统现成机制：从 4.5 级联重跑 figure_describe → fts → vectors → graph，前置产物复用）；
- 串行或低并发排队（VLM 走 dgx，`figure_describe_slot` 自带排队/取消）；
- 本地与生产**各跑各的**（两端产物均在，各自重跑即可，无需同步）；
- 单篇跑完该篇"图 N"类问题即可答。建议脚本按 doc_list 过滤"有 mineru_raw 产物且无 figure_describe 记录"生成队列。

### 阶段 2（按用户节奏，不催）：B 类 83 篇随重新上传自然补齐
- 前提：**用户手里有原始 PDF/DOCX**（源文件双端已丢失）；
- 正确姿势：**不删节点**。源文件放回 `libraries/default/documents/{doc_id}/source/`，从
  `raw_parse` 阶段起按文档重跑解析（doc_id 不变，引用/关联不断链），图描述与 render_pdf 自然产出；
- 成本参考：mineru 对 300 页 PDF 约 10-30 分钟 GPU/篇；83 篇全量 ≈ 一整夜。**建议按使用频率分批**，
  常用规范先做；不做的代价仅是溯源 PDF 视图与图描述，问答不受影响；
- ❌ 明确不做：删节点全库重解析（doc_id 漂移、断关联、浪费已修好的 20 万行向量索引，零收益）。

## 附带观察（顺手修与否随意）

- `SQLiteVectorStore.get_existing_dimension()` 以 **rowid 最后一行**的维度作为全库期望维度——
  混入一行异构维度即可让全库语义检索静默瘫痪（2026-09-06 生产故障实况：291 行 2560 维遗留毒倒了 4.4 万行正常数据）。
  建议改为多数表决或写入时强校验。
- 拒答重答守卫对"结构上根本答不了"的问题（如引用不存在的"图 N"索引）会白白多烧一轮检索（实测 +20 秒级）。

## 事故档案索引

恢复全过程工具与备份：`data/recovery/`（doc_list / vectors_done / refill / reembed / vec_sync 导出，
快照 `snapshot-20260905.sqlite` 建议 2026-09-13 后清理）；数据库备份 `*.bak-recovery-20260906*`（本地）与
`*.bak-recovery-20260906pm`（生产）。防护修复见 commit `8378e13`（clean-orphaned 以数据库实况判定 + 批量护栏）。
