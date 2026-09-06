"""按题型汇总评测结果并生成 Markdown 报告（CLI 薄壳）。

算法真相源在 evals_core.nightly.report（统计口径：N/A 不进分母、均值配 median/p90 看），
本模块只保留 raw/manifest 读写与落盘。
"""
import argparse
import os
import sys

from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from open_ragbench import common
from evals_core.nightly import report as _report

# 算法真相源 re-export（保持既有调用面不变）
SOURCES = _report.SOURCES
_mean = _report._mean
_median_p90 = _report._median_p90
bootstrap_ci = _report.bootstrap_ci
summarize_bucket = _report.summarize_bucket
group_and_summarize = _report.group_and_summarize
render_markdown = _report.render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="生成评测报告（算法在 evals_core.nightly.report）")
    parser.add_argument("--raw", default=str(common.REPORTS_DIR / "open-ragbench-subset-v1-raw.json"))
    parser.add_argument("--out", default=str(common.REPORTS_DIR / "open-ragbench-subset-v1.md"))
    parser.add_argument("--manifest", default=str(common.SUBSET_MANIFEST), help="子集 manifest（题型归属）")
    parser.add_argument("--resamples", type=int, default=1000, help="bootstrap 重采样次数")
    args = parser.parse_args()
    run = common.load_json(Path(args.raw))
    manifest = common.load_json(Path(args.manifest))
    summary = group_and_summarize(run.get("details") or [], manifest, ci_resamples=args.resamples)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(summary), encoding="utf-8")
    print(f"报告已生成: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
