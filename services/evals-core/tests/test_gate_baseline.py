"""gate.load_baseline 指针路径解析回归。

事故（2026-09-07 nightly）：基线在 Windows 机器钉住后拷到 Linux 服务器，指针 raw 为
"data\\evals\\baseline\\<file>"（反斜杠）；POSIX Path().name 不切反斜杠，整串被当文件名
拼出 /app/data/evals/baseline/data\\evals\\baseline\\<file> 双重路径 → FileNotFoundError，
nightly 无结论失败。修复：读侧先归一化分隔符（gate），写侧存 as_posix（compare_runs pin）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

EVALS_CORE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(EVALS_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(EVALS_CORE_SRC))

from evals_core.nightly import gate  # noqa: E402

SNAPSHOT = {
    "run_id": "run-abc123",
    "dataset_id": "open-ragbench-subset-v2",
    "status": "completed",
    "details": [],
}


class LoadBaselinePathTests(unittest.TestCase):
    def _make_baseline_dir(self, raw: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        json.dump({"label": "L1", "run_id": SNAPSHOT["run_id"],
                   "dataset_id": SNAPSHOT["dataset_id"], "raw": raw},
                  open(base / "baseline_run.json", "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(SNAPSHOT,
                  open(base / "open-ragbench-subset-v2-run-abc123.baseline.json",
                       "w", encoding="utf-8"), ensure_ascii=False)
        self._tmp = tmp
        return base

    def tearDown(self) -> None:
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_windows_sep_raw_resolves(self):
        """Windows 钉的基线（反斜杠 raw）在 Linux 上也能按文件名解析（回归 2026-09-07 nightly 事故）。"""
        base = self._make_baseline_dir(r"data\evals\baseline\open-ragbench-subset-v2-run-abc123.baseline.json")
        loaded = gate.load_baseline(base)
        self.assertEqual(loaded.get("run_id"), "run-abc123")
        self.assertEqual(loaded.get("_baseline_label"), "L1")

    def test_posix_raw_resolves(self):
        """as_posix 新格式（pin 修复后）正常解析。"""
        base = self._make_baseline_dir("data/evals/baseline/open-ragbench-subset-v2-run-abc123.baseline.json")
        loaded = gate.load_baseline(base)
        self.assertEqual(loaded.get("run_id"), "run-abc123")

    def test_plain_filename_raw_resolves(self):
        """纯文件名形态（与指针同目录）正常解析。"""
        base = self._make_baseline_dir("open-ragbench-subset-v2-run-abc123.baseline.json")
        loaded = gate.load_baseline(base)
        self.assertEqual(loaded.get("run_id"), "run-abc123")


if __name__ == "__main__":
    unittest.main()
