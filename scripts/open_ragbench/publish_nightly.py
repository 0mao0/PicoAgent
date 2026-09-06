"""把门禁产物目录烘焙成单日结论（CLI 薄壳；服务内流水线直接调 evals_core.nightly.archive）。

"发布"仅指写数据文件（<target>/<YYYY-MM-DD>/{nightly.json, report.md}），与代码
push/系统发版无关。结论构建与清理的真相源在 evals_core.nightly.archive。
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from open_ragbench import common
from evals_core.nightly import archive as _archive

KEEP_DAYS_DEFAULT = _archive.KEEP_DAYS_DEFAULT
DATASET_DEFAULT = "open-ragbench-subset-v2"
REGRESSION_ITEMS_MAX = _archive.REGRESSION_ITEMS_MAX
FIXED_ITEMS_MAX = _archive.FIXED_ITEMS_MAX
verdict = _archive.verdict
prune_old = _archive.prune_old


def _load_json(path: Path):
    try:
        return common.load_json(path)
    except (OSError, ValueError):
        return None


def build_nightly_entry(artifacts_dir: Path, dataset_id: str, date: str, error_note: str = "",
                        dataset_file: Path = None) -> dict:
    """合并 workflow 产物目录（gate.json/raw.json）为单日条目；gate 缺失降级 error。"""
    gate = _load_json(Path(artifacts_dir) / "gate.json")
    raw = _load_json(Path(artifacts_dir) / "raw.json")
    if not isinstance(gate, dict):
        return _archive.build_error_entry(dataset_id, date,
                                          error_note or "未产出门禁结论（上游步骤未完成）")
    question_texts = (_archive.load_question_texts(dataset_file) if dataset_file else {})
    state = "red" if gate.get("gate_red") else "green"
    summary = (raw or {}).get("summary_scores") or {}
    subject = ""
    if dataset_file:
        meta = (_load_json(Path(dataset_file)) or {}).get("dataset") or {}
        subject = str(meta.get("title") or "")
    return _archive.build_entry(
        gate, summary, question_texts, dataset_id, date,
        run_id=gate.get("new") or (raw or {}).get("run_id") or "", state=state, subject=subject)


def main() -> int:
    parser = argparse.ArgumentParser(description="烘焙单日夜间维护结论（算法在 evals_core.nightly.archive）")
    parser.add_argument("--artifacts", required=True, help="workflow 产物目录（含 gate.json/raw.json/report.md）")
    parser.add_argument("--target", required=True, help="站点数据根（如 /home/runner/AnGIneer/data/evals/nightly）")
    parser.add_argument("--dataset-id", default=DATASET_DEFAULT)
    parser.add_argument("--date", default="", help="覆盖日期（YYYY-MM-DD），默认取北京时间今天")
    parser.add_argument("--keep-days", type=int, default=KEEP_DAYS_DEFAULT)
    parser.add_argument("--error-note", default="", help="产物缺失时写入的历史备注（步骤结论等）")
    parser.add_argument("--dataset-file", default="",
                        help="题集 JSON（用于回退/修复题的题干摘录；缺省则题目仅带 qid）")
    args = parser.parse_args()

    from evals_core.nightly import paths as _paths
    date = args.date or _paths.today_bjt()
    entry = build_nightly_entry(
        Path(args.artifacts), args.dataset_id, date, args.error_note,
        Path(args.dataset_file) if args.dataset_file else None,
    )
    report_src = Path(args.artifacts) / "report.md"
    report_md = report_src.read_text(encoding="utf-8") if report_src.exists() else None
    day_dir = _archive.publish_day(entry, report_md, root=Path(args.target), keep_days=args.keep_days)
    print(f"已发布 {day_dir}（state={entry['state']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
