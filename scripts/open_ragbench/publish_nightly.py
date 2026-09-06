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


def _today_bjt() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime(_DATE_FMT)


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build_nightly_entry(artifacts_dir: Path, dataset_id: str, date: str, error_note: str = "") -> dict:
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
            "note": error_note or "未产出门禁结论（上游步骤未完成）",
        }
    matrix = {k: (gate.get("matrix") or {}).get(k) for k in ("pp", "pf", "fp", "ff")}
    return {
        "date": date,
        "state": "red" if gate.get("gate_red") else "green",
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
        "regressions": gate.get("regressions") or {},
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
    args = parser.parse_args()

    artifacts = Path(args.artifacts)
    root = Path(args.target)
    date = args.date or _today_bjt()
    entry = build_nightly_entry(artifacts, args.dataset_id, date, args.error_note)

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
