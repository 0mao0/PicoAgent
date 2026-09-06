"""clean-orphaned 事故回归（2026-09-06 误删 102 条）：
1) 孤儿判定必须以数据库 nodes 表为准，进程内存快照 ks.nodes 在换库/热替换后不可信；
2) 一次性拟清理数量超过安全阈值时必须拒绝执行（409 + 明细），除非显式 confirm。
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/docs-api")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/docs-core/src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/angineer-core/src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/tree-core/src")))

import docs_routes  # noqa: E402
import models.parse_record as parse_record  # noqa: E402
from fastapi import HTTPException  # noqa: E402

# 期望实现直查存活节点表，判定关键词（测试侧仅做包含性断言）
LIVE_NODE_QUERY_MARKERS = ("nodes", "deleted=0")


def fake_ks(live_ids, memory_ids):
    """meta_store 取数走 mock：返回预置存活 id，并记录被调用的语句文本。"""
    ks = MagicMock()
    conn = ks.meta_store.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchall.return_value = [(i,) for i in sorted(set(live_ids))]
    ks.meta_store_conn = conn
    ks.nodes = [MagicMock(id=i) for i in memory_ids]
    return ks


class CleanOrphanedDbTruthTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp_dir, ignore_errors=True))
        self.patcher = patch.object(parse_record, "DB_PATH", os.path.join(self.tmp_dir, "parse_records.sqlite"))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _assert_queried_live_nodes(self, ks):
        conn = ks.meta_store_conn
        conn.execute.assert_called()
        statement = str(conn.execute.call_args.args[0]).lower()
        for marker in LIVE_NODE_QUERY_MARKERS:
            self.assertIn(marker, statement)

    def test_db_has_node_but_memory_stale_must_not_be_cleaned(self):
        """事故复现：库里(数据库)有节点、内存快照没有 → 绝不能判孤儿。"""
        parse_record.insert_record(parse_record.ParseRecord(doc_id="doc-0bc3a8f6", task_id="t1"))
        ks = fake_ks(live_ids=["doc-0bc3a8f6"], memory_ids=[])
        cleaned = docs_routes._clean_orphaned_records(ks)
        self.assertEqual(cleaned, 0)
        self._assert_queried_live_nodes(ks)
        # "只看已删"清单里不应出现它
        self.assertEqual(
            [r for r in parse_record.list_records(deleted_filter=True) if r["doc_id"] == "doc-0bc3a8f6"],
            [],
        )

    def test_db_without_node_is_cleaned(self):
        parse_record.insert_record(parse_record.ParseRecord(doc_id="doc-ghost", task_id="t1"))
        ks = fake_ks(live_ids=[], memory_ids=[])
        cleaned = docs_routes._clean_orphaned_records(ks)
        self.assertEqual(cleaned, 1)
        rows = [r for r in parse_record.list_records(deleted_filter=True) if r["doc_id"] == "doc-ghost"]
        self.assertEqual(len(rows), 1)

    def test_guardrail_rejects_mass_cleanup_without_confirm(self):
        for i in range(docs_routes.ORPHAN_CLEAN_GUARD_LIMIT + 1):
            parse_record.insert_record(parse_record.ParseRecord(doc_id=f"doc-{i}", task_id="t1"))
        ks = fake_ks(live_ids=[], memory_ids=[])
        with self.assertRaises(HTTPException) as ctx:
            docs_routes._clean_orphaned_records(ks)
        self.assertEqual(ctx.exception.status_code, 409)
        # 拒绝执行 = 一条都不许标
        rows = [r for r in parse_record.list_records(deleted_filter=True)]
        self.assertEqual(rows, [])

    def test_guardrail_overridable_with_confirm(self):
        for i in range(docs_routes.ORPHAN_CLEAN_GUARD_LIMIT + 1):
            parse_record.insert_record(parse_record.ParseRecord(doc_id=f"doc-{i}", task_id="t1"))
        ks = fake_ks(live_ids=[], memory_ids=[])
        cleaned = docs_routes._clean_orphaned_records(ks, confirm=True)
        self.assertEqual(cleaned, docs_routes.ORPHAN_CLEAN_GUARD_LIMIT + 1)


if __name__ == "__main__":
    unittest.main()
