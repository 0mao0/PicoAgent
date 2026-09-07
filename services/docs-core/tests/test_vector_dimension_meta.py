"""期望维度 meta 持久化的回归测试。

背景（2026-09-07 生产事故）：get_existing_dimension 原为每次全表多数表决，
embedding_provider 在模块导入期调用它 → 5GB 级向量库每次容器启动被拖死 15+ 分钟。
修复后：index_meta 持久化期望维度，稳态读取 O(1)；表决仅作为 meta 缺失时的
一次性回填（旧库首开 / strict=False 整库迁移后）。
"""
import numpy as np
import pytest

from docs_core.step06_vectors.sqlite_vector_store import SQLiteVectorStore
from docs_core.step06_vectors.vector_store import VectorRecord

DIM_KEY = SQLiteVectorStore._META_DIM_KEY


@pytest.fixture()
def store(tmp_path):
    return SQLiteVectorStore(db_path=tmp_path / "vectors.sqlite")


def _record(record_id: str, embedding) -> VectorRecord:
    return VectorRecord(
        record_id=record_id,
        doc_id="doc-x",
        entity_type="chunk",
        entity_id=record_id,
        content=f"内容-{record_id}",
        metadata={"doc_id": "doc-x"},
        embedding=embedding,
    )


def _meta(store):
    with store.connect() as conn:
        row = conn.execute("SELECT value FROM index_meta WHERE key = ?", (DIM_KEY,)).fetchone()
        return int(row["value"]) if row else None


def test_empty_db_returns_zero_without_meta(store):
    assert store.get_existing_dimension() == 0
    assert _meta(store) is None  # 空库无可表决，不落 meta（首笔写入仍可重算）


def test_meta_first_path_is_authoritative_without_scan(store):
    # 直接种入 meta（模拟服务器已 seed 的存量库）→ 空表也能 O(1) 返回
    with store.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)", (DIM_KEY, "1024"))
        conn.commit()
    assert store.get_existing_dimension() == 1024
    assert _meta(store) == 1024


def test_vote_runs_once_and_persists_meta(store):
    store.upsert_records(
        [_record(f"r{i}", [float(i)] * 1024) for i in range(3)]
        + [_record("bad", [0.9] * 2560)]
    )
    # 无 meta → 多数表决取 1024，并落 meta
    assert store.get_existing_dimension() == 1024
    assert _meta(store) == 1024
    # 清空向量后 meta 仍权威（稳态不再依赖行内容，无需重扫）
    with store.connect() as conn:
        conn.execute("DELETE FROM canonical_vectors")
        conn.commit()
    assert store.get_existing_dimension() == 1024


def test_migration_clears_meta_for_revote(store):
    store.upsert_records([_record("a", [0.1] * 1024)], strict_dimension=False)
    assert _meta(store) is None  # 迁移路径删除 meta
    store.upsert_records([_record("b", [0.2] * 2560)], strict_dimension=False)
    store.upsert_records([_record("c", [0.3] * 2560), _record("d", [0.4] * 2560)])
    # 新库多数为 2560 → 表决回填
    assert store.get_existing_dimension() == 2560
    assert _meta(store) == 2560


def test_hetero_write_still_rejected_by_guard(store):
    store.upsert_records([_record("a", np.zeros(1024))], strict_dimension=False)
    store.upsert_records([_record("b", np.zeros(1024))])
    with pytest.raises(ValueError, match="拒绝写入异构维度向量"):
        store.upsert_records([_record("bad", np.zeros(2560))])
