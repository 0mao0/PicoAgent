"""启动清扫所有权守卫：running 只在属主进程确实死亡时才被标 cancelled。

回归 2026-09-06 事故：多实例共用 evals.sqlite 时，后启动实例的清扫把前一个
还活着的实例正在跑的 run（53/487）误标为 cancelled，评测在"没有任何错误"
的情况下被判死。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SRC = TESTS_DIR.parent / "src"
for p in (str(SRC), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from evals_core.runner.suite_runner import _pid_alive, sweep_interrupted_runs
from evals_core.storage import result_store

DEAD_PID = 99999999


class EvalsDbCase(unittest.TestCase):
    """临时库切换；Windows 上必须先关连接再删临时目录。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_db = result_store._DB_PATH
        self._orig_local = result_store._LOCAL
        result_store._DB_PATH = str(Path(self._tmp.name) / "evals.sqlite")
        result_store._LOCAL = None
        result_store.init_db()

    def tearDown(self):
        try:
            conn = result_store._get_conn()
        except Exception:
            conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        result_store._LOCAL = None
        result_store._DB_PATH = self._orig_db
        self._tmp.cleanup()

    def insert_run(self, run_id: str, owner_pid: int) -> None:
        conn = result_store._get_conn()
        conn.execute(
            "INSERT INTO eval_run (run_id, dataset_id, status, total_questions, completed_questions, started_at, owner_pid) "
            "VALUES (?, 'ds-x', 'running', 10, 3, '2026-09-06T20:00:00', ?)",
            (run_id, owner_pid),
        )
        conn.commit()


class TestPidAlive(unittest.TestCase):
    def test_self_is_alive(self):
        self.assertTrue(_pid_alive(os.getpid()))

    def test_dead_and_invalid_pids(self):
        self.assertFalse(_pid_alive(DEAD_PID))
        self.assertFalse(_pid_alive(0))
        self.assertFalse(_pid_alive(-1))


class TestSweepOwnerGuard(EvalsDbCase):
    def test_alive_owner_run_is_never_swept(self):
        """活体 run（owner=当前进程）不得被清扫——这是 53/487 事故的守卫。"""
        self.insert_run("run-alive-owner", os.getpid())
        self.assertEqual(sweep_interrupted_runs(), 0)
        self.assertEqual(result_store.get_run("run-alive-owner")["status"], "running")

    def test_dead_owner_run_is_swept(self):
        self.insert_run("run-dead-owner", DEAD_PID)
        self.assertEqual(sweep_interrupted_runs(), 1)
        run = result_store.get_run("run-dead-owner")
        self.assertEqual(run["status"], "cancelled")
        # 部分汇总按已完成明细真实统计（明细为空 → correct/wrong 均 0，skipped=10）
        self.assertEqual(run["summary_scores"]["skipped"], 10)

    def test_legacy_zero_pid_run_is_swept(self):
        """历史行 owner_pid=0 无法判属主，照旧回收（不改变旧行为）。"""
        self.insert_run("run-legacy", 0)
        self.assertEqual(sweep_interrupted_runs(), 1)
        self.assertEqual(result_store.get_run("run-legacy")["status"], "cancelled")


class TestCreateRunRecordsOwner(EvalsDbCase):
    def test_create_run_and_resume_stamp_owner_pid(self):
        created = result_store.create_run("ds-x", 5)
        conn = result_store._get_conn()
        pid = conn.execute(
            "SELECT owner_pid FROM eval_run WHERE run_id = ?", (created["run_id"],)
        ).fetchone()[0]
        self.assertEqual(pid, os.getpid())
        result_store.cancel_run(created["run_id"], {})
        result_store.reset_run_for_resume(created["run_id"], {"answer_model": "m"})
        pid2 = conn.execute(
            "SELECT owner_pid FROM eval_run WHERE run_id = ?", (created["run_id"],)
        ).fetchone()[0]
        self.assertEqual(pid2, os.getpid())


if __name__ == "__main__":
    unittest.main()
