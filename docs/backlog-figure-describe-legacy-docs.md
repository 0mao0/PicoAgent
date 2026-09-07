# 待办：存量文档图描述补齐 与 83 篇产物重建

> 状态：**阶段 1（存量图描述补齐）已于 2026-09-07 凌晨全部完成**；阶段 2（产物重建）因源文件找到而变为可行，
> 剩余仅溯源 PDF 视图降级与本地完整重建，挂账待用户排期。

## 起因

VLM 图描述功能上线前的存量文档没有图简介索引；部分文档解析产物在 2026-09-06 误删事故中于**本地**丢失
（生产侧产物当时已从 9-05 快照完整回灌，backlog 原记"双端丢失"不准确——只有本地丢了）。

## 完成记录（2026-09-06 22:00 – 2026-09-07 03:00）

### 阶段 1：存量 103 篇图描述全部补齐（A 类 26 + 生产独有 77）

| 类别 | 篇数 | 做法 | 结果 |
|---|---|---|---|
| 本地有产物、缺图描述（原"A 类"） | 22 篇 doc-* + 4 篇 v1-* = 26 | 本地逐篇 retry figure_describe（级联 fts/vectors/graph），VLM=dgx 唯一一次 GPU | 26/26 succeeded 零失败 |
| 仅生产有产物（原以为"双端丢失"） | 77 篇 doc-*（lib-261558be） | 生产侧逐篇 retry（VLM 直跑，~2 分钟/篇），本地无原料故不重复 | 77/77 完成（4 篇曾被 fts database is locked/读超时误记 failed，服务端实际全部完成，终验清零） |
| 产物在手但 jsonl 无任何图表块 | 4 篇 | 无需跑（避免白重建索引） | skipped |

- 两端重叠的 26 篇走**产物同步**：本地跑完 VLM 后把 `doc_blocks_graph.jsonl` scp 到生产，生产重触发时
  图描述阶段断点跳过（零 VLM 调用），只重建索引。
- 生产新生成的 77 份 jsonl 已于收尾时倒灌回本地（`libraries/lib-261558be/...`，77/77 抽检图块带描述）；
  本地零 VLM 重索引（fts/vectors/graph）于 2026-09-07 晨执行（若完成，本地与生产重新同构）。
- 工具：`scripts/open_ragbench/backfill_figure_descriptions.py`（本次升级：`--from-db` 自动筛队列/`--dry-run`/
  管理员 Bearer 轮询/`--token`/连接异常重试/兼容旧 python，commit `ea186da`）。
- 收尾日志归档：服务器 `data/recovery/fig_backfill_20260907/`（run77/runfix/chain 日志与清单）。
- 运维记录：生产临时管理员会话已删除；`/root/figbak` 临时工具目录已清理。

### 阶段 2 新发现：77 篇源文件全数在手 → 本地完整重建变为可行

- 用户目录 `D:\AI\07智能建造\施工组织方案`（262 文件）与 77 篇逐一匹配：**77/77 命中**
  （55 PDF + 22 DOCX，文件名=「PJ 编号_项目_公司_施工组织设计」）。
- 正确姿势不变：不删节点；源文件放回 `libraries/default|lib-261558be/documents/{doc_id}/source/`
  （文件名须与 nodes.file_path 一致），从 `raw_parse` 阶段按文档重跑，图描述与 render_pdf 自然产出。
- **本地重跑的代价警告**：见下方遗留项 A——批量重解析会把 4GB 生产机打成内存抖动半挂，本地无此约束，
  生产补解析必须挑低峰/分批，或先修遗留项 A。

## 遗留项（需排期）

- **A. docs-api 常驻向量矩阵缓存在 4GB 生产机上撑不起批量重解析**（2026-09-07 凌晨实踩两次）：
  每篇写库 → mtime 变 → 全表向量 JSON 重载（约 8 百 MB 级矩阵）→ 与解析峰值叠加 → 4GB swap 打穿、
  load>100、站点/sshd 假死，内核 OOM 杀 uvicorn（dmesg：anon-rss 2.87GB / 3.1GB 各一次）自愈后循环。
  方向：缓存上限/float16/挪出 web worker；解析任务与检索流量错峰。本次靠重启 + 错峰收尾，未根治。
- ~~`SQLiteVectorStore.get_existing_dimension()` 以 rowid 最后一行为全库期望维度~~（已修：commit `83797be`
  多数表决 + upsert 默认拒写异构维度 + 6 测试）。
- 拒答重答守卫对"结构上根本答不了"的问题（如引用不存在的"图 N"索引）多烧一轮检索（+20 秒级），未动。

## 事故档案索引

恢复全过程工具与备份：`data/recovery/`（doc_list / vectors_done / refill / reembed / vec_sync 导出，
快照 `snapshot-20260905.sqlite` 建议 2026-09-13 后清理）；数据库备份 `*.bak-recovery-20260906*`（本地）与
`*.bak-recovery-20260906pm`（生产）。防护修复见 commit `8378e13`（clean-orphaned 以数据库实况判定 + 批量护栏）。
图描述补跑档案：生产 `data/recovery/fig_backfill_20260907/`。
