"""「重来」原地重跑：restart_run_for_retry 复用同一 run 记录、清空旧明细与进度。"""
import sys
import unittest
from pathlib import Path


EVALS_CORE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(EVALS_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(EVALS_CORE_SRC))

from evals_core.storage import result_store  # noqa: E402


class RestartRunTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._saved_path = result_store._DB_PATH
        result_store._DB_PATH = str(Path(self._tmp.name) / "evals.sqlite")
        # 线程级连接缓存指向旧库：必须重置后才连到新临时库
        local = result_store._get_thread_local()
        saved_conn = getattr(local, "conn", None)
        self._saved_conn = saved_conn
        if saved_conn:
            saved_conn.close()
        local.conn = None
        result_store.init_db()

    def tearDown(self):
        local = result_store._get_thread_local()
        conn = getattr(local, "conn", None)
        if conn:
            conn.close()
        local.conn = self._saved_conn
        result_store._DB_PATH = self._saved_path
        self._tmp.cleanup()

    def test_restart_resets_run_and_clears_details(self):
        run = result_store.create_run("ds-restart", 3, run_name="m_0101-0000")
        run_id = run["run_id"]
        for qid in ("q1", "q2"):
            result_store.insert_run_detail({
                "run_id": run_id, "question_id": qid,
                "status": "completed", "quality": "correct", "scores": {"score": 1},
            })
        result_store.update_run_progress(run_id, 2)
        result_store.complete_run(run_id, {"overall_score": 1.0, "correct": 2})

        result_store.restart_run_for_retry(run_id, {"model": "m"})

        conn = result_store._get_conn()
        row = conn.execute("SELECT * FROM eval_run WHERE run_id = ?", (run_id,)).fetchone()
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["completed_questions"], 0)
        self.assertIsNone(row["summary_scores"])
        self.assertIsNone(row["completed_at"])
        details = conn.execute("SELECT * FROM eval_run_detail WHERE run_id = ?", (run_id,)).fetchall()
        self.assertEqual(len(details), 0)
        # 复用同一记录：没有新增第二条
        self.assertEqual(conn.execute("SELECT count(*) FROM eval_run").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
