"""发布 nightly 产物到站点目录（评测集页「夜间维护」视图的数据源）。

workflow 在 gate/report 之后（if: always()）调用：
- 门禁产物齐全 → 合并 gate.json + raw.json summary 为单日 nightly.json，并拷 report.md；
- 产物缺失（评测/报告中途失败）→ 也落一天 state=error 记录，保证历史不断档；
- 按日期清理超过 keep-days 的旧目录（与 GH artifacts 30 天对齐）。

目标目录约定：<target>/<YYYY-MM-DD>/{nightly.json, report.md}，由 aichat-api
GET /api/evals/nightly[/日期] 只读消费（目录名严格日期，接口侧防穿越）。
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP_DAYS_DEFAULT = 30
DATASET_DEFAULT = "open-ragbench-subset-v2"
_DATE_FMT = "%Y-%m-%d"
# 明细条目上限（nightly.json 要直接进接口/前端，不能带全量逐题数据）
REGRESSION_ITEMS_MAX = 50
FIXED_ITEMS_MAX = 20
_QUESTION_MAX = 300


def _verdict(state: str, delta, regress_count: int) -> str:
    """≤20 字一句话评价（表格「评价」列）：pp 取整，精确小数留给「基线」列，两处不重复。
    措辞面向普通读者：不写"回归/门禁"等内部术语。"""
    if state == "error":
        return "评测中断，未出结果"
    if state == "red":
        return f"回退 {regress_count} 题，需排查" if regress_count else "整体变差，需排查"
    if delta is None:
        return "无基线可比，未见变差"
    pp = round(delta * 100)
    if pp >= 1:
        return f"提升 {pp}pp，没有题目变差"
    if pp <= -1:
        return f"回落 {abs(pp)}pp，正常波动"
    return "与基线持平，没有变差"


def _load_question_texts(dataset_file) -> dict:
    """从题集 JSON 取 qid→题干（run 明细不带题干，发布端补齐给前端做人话展示）。"""
    try:
        data = json.loads(Path(dataset_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    # 题集导出格式 {"items":[...]}（evals 导入件）与子集 manifest {"questions":[...]} 都兼容
    rows = data.get("items") or data.get("questions") if isinstance(data, dict) else None
    for q in rows or []:
        if not isinstance(q, dict):
            continue
        qid, text = q.get("question_id") or q.get("uuid"), str(q.get("question") or "")
        if qid and text:
            out[qid] = text[:_QUESTION_MAX]
    return out


def _question_items(qids, buckets: dict, question_texts: dict, limit: int) -> list:
    items = []
    for qid in list(qids)[:limit]:
        bucket = str(buckets.get(qid) or "")
        items.append({
            "qid": qid,
            "question": question_texts.get(qid, ""),
            "bucket": bucket.split("(", 1)[0],  # 机读码，前端映射大白话；原始串留 tooltip
            "bucket_detail": bucket,
        })
    return items


def _today_bjt() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime(_DATE_FMT)


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build_nightly_entry(artifacts_dir: Path, dataset_id: str, date: str, error_note: str = "",
                        dataset_file: Path = None) -> dict:
    """合并门禁产物为单日条目；产物缺失降级 error，绝不抛异常（发布步骤必须落盘）。"""
    gate = _load_json(artifacts_dir / "gate.json")
    raw = _load_json(artifacts_dir / "raw.json")
    summary = (raw or {}).get("summary_scores") or {}
    if not isinstance(gate, dict):
        return {
            "date": date,
            "state": "error",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_id": dataset_id,
            "verdict": _verdict("error", None, 0),
            "note": error_note or "未产出门禁结论（上游步骤未完成）",
        }
    matrix = {k: (gate.get("matrix") or {}).get(k) for k in ("pp", "pf", "fp", "ff")}
    state = "red" if gate.get("gate_red") else "green"
    regressions = gate.get("regressions") or {}
    question_texts = _load_question_texts(dataset_file) if dataset_file else {}
    reg_ids = [qid for qid, _ in sorted(regressions.items(), key=lambda kv: (kv[1], kv[0]))]
    return {
        "date": date,
        "state": state,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": gate.get("new") or (raw or {}).get("run_id") or "",
        "dataset_id": dataset_id,
        "overall_score": summary.get("overall_score"),
        "correct": summary.get("correct"),
        "total": summary.get("total"),
        "errored": summary.get("errored"),
        "judge_failed_count": summary.get("judge_failed_count"),
        "delta": gate.get("delta"),
        "delta_ci95": gate.get("delta_ci95"),
        "base_label": gate.get("base_label"),
        "matrix": matrix,
        "gate_reasons": gate.get("gate_reasons") or [],
        "regressions": regressions,
        "verdict": _verdict(state, gate.get("delta"), len(regressions)),
        "regression_items": _question_items(reg_ids, regressions, question_texts, REGRESSION_ITEMS_MAX),
        "fixed_items": _question_items(gate.get("fixed") or [], {}, question_texts, FIXED_ITEMS_MAX),
    }


def prune_old(target_root: Path, keep_days: int, today: str) -> list:
    """按日期名清理旧目录（目录名不合法日期的不动，人工排查留证）。"""
    removed = []
    try:
        floor = (datetime.strptime(today, _DATE_FMT) - timedelta(days=keep_days)).strftime(_DATE_FMT)
    except ValueError:
        return removed
    for day in sorted(target_root.iterdir()):
        if not day.is_dir():
            continue
        try:
            datetime.strptime(day.name, _DATE_FMT)
        except ValueError:
            continue
        if day.name < floor:
            shutil.rmtree(day, ignore_errors=True)
            removed.append(day.name)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="发布 nightly 产物到站点夜间维护目录")
    parser.add_argument("--artifacts", required=True, help="workflow 产物目录（含 gate.json/raw.json/report.md）")
    parser.add_argument("--target", required=True, help="站点数据根（如 /home/runner/AnGIneer/data/evals/nightly）")
    parser.add_argument("--dataset-id", default=DATASET_DEFAULT)
    parser.add_argument("--date", default="", help="覆盖日期（YYYY-MM-DD），默认取北京时间今天")
    parser.add_argument("--keep-days", type=int, default=KEEP_DAYS_DEFAULT)
    parser.add_argument("--error-note", default="", help="产物缺失时写入的历史备注（步骤结论等）")
    parser.add_argument("--dataset-file", default="",
                        help="题集 JSON（用于回退/修复题的题干摘录；缺省则题目仅带 qid）")
    args = parser.parse_args()

    artifacts = Path(args.artifacts)
    root = Path(args.target)
    date = args.date or _today_bjt()
    entry = build_nightly_entry(
        artifacts, args.dataset_id, date, args.error_note,
        Path(args.dataset_file) if args.dataset_file else None,
    )

    day_dir = root / date
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "nightly.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    report_src = artifacts / "report.md"
    if report_src.exists():
        shutil.copyfile(report_src, day_dir / "report.md")

    removed = prune_old(root, args.keep_days, date)
    print(f"已发布 {day_dir}（state={entry['state']}），清理 {len(removed)} 个过期目录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
