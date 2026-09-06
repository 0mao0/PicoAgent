"""SQLiteVectorStore 全量矩阵缓存的回归测试。

覆盖点：
- 分批流式构建（小 batch 走多批路径）后 rows/valid_idx/matrix 对齐语义不变；
- 常驻 rows 不再保留 embedding_json 原文（内存约束回归点）；
- 写入后缓存失效、检索结果正确。
"""
import numpy as np
import pytest

from docs_core.step06_vectors import sqlite_vector_store as svs
from docs_core.step06_vectors.sqlite_vector_store import SQLiteVectorStore
from docs_core.step06_vectors.vector_store import VectorRecord


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """独立临时库 + 隔离的模块级缓存 + 小批次（强制多批构建）。"""
    saved_cache = dict(svs._VECTOR_CACHE)
    monkeypatch.setattr(svs, "_CACHE_BUILD_BATCH_SIZE", 2)
    svs._VECTOR_CACHE.update({"loaded_mtime": None, "rows": None, "matrix": None})
    yield SQLiteVectorStore(db_path=tmp_path / "vectors.sqlite")
    svs._VECTOR_CACHE.clear()
    svs._VECTOR_CACHE.update(saved_cache)


def _record(record_id: str, doc_id: str, embedding, entity_type: str = "chunk") -> VectorRecord:
    return VectorRecord(
        record_id=record_id,
        doc_id=doc_id,
        entity_type=entity_type,
        entity_id=record_id,
        content=f"内容-{record_id}",
        metadata={"doc_id": doc_id},
        embedding=embedding,
    )


def test_batched_cache_build_alignment(store):
    store.upsert_records([
        _record("r1", "doc-a", [1.0, 0.0, 0.0]),
        _record("r2", "doc-a", []),  # 空向量 → 无效，不进矩阵
        _record("r3", "doc-b", [0.0, 1.0, 0.0]),
        _record("r4", "doc-b", [0.0, 0.0, 1.0]),
        _record("r5", "doc-a", [1.0, 1.0, 0.0]),
    ])
    store._ensure_cache()
    cache = svs._VECTOR_CACHE
    assert len(cache["rows"]) == 5  # rows 与全表对齐（含无效行）
    assert cache["valid_idx"] == [0, 2, 3, 4]  # 仅有效向量
    assert cache["matrix"].shape == (4, 3)
    assert cache["dimension"] == 3
    # 常驻 rows 不保留 embedding_json 原文
    assert all("embedding_json" not in row for row in cache["rows"])


def test_search_after_batched_build(store):
    store.upsert_records([
        _record("r1", "doc-a", [1.0, 0.0, 0.0]),
        _record("r2", "doc-a", [0.0, 1.0, 0.0]),
        _record("r3", "doc-b", [0.0, 0.0, 1.0]),
    ])
    hits = store.search([1.0, 0.0, 0.0], top_k=5)
    assert [hit.record_id for hit in hits][:1] == ["r1"]

    # doc_ids 过滤
    hits_b = store.search([1.0, 0.0, 0.0], doc_ids=["doc-b"], top_k=5)
    assert [hit.record_id for hit in hits_b] == ["r3"]

    # entity_types 过滤
    hits_none = store.search([1.0, 0.0, 0.0], entity_types=["table_schema"], top_k=5)
    assert hits_none == []


def test_cache_invalidated_on_write(store):
    store.upsert_records([_record("r1", "doc-a", [1.0, 0.0])])
    store._ensure_cache()
    assert svs._VECTOR_CACHE["matrix"] is not None
    store.upsert_records([_record("r2", "doc-a", [0.0, 1.0])])
    assert svs._VECTOR_CACHE["loaded_mtime"] is None  # 写操作强制失效
    hits = store.search([0.0, 1.0], top_k=5)
    assert [hit.record_id for hit in hits][:1] == ["r2"]


def test_dimension_mismatch_returns_empty(store):
    store.upsert_records([_record("r1", "doc-a", [1.0, 0.0])])
    assert store.search([1.0, 0.0, 0.0], top_k=5) == []


def test_existing_dimension_empty_store(store):
    assert store.get_existing_dimension() == 0


def test_existing_dimension_majority_vote(store):
    # 多数派 3 维 5 行；2 维 2 行、5 维 1 行（含最后一行 5 维）都不应左右期望维度
    store.upsert_records([_record(f"m{i}", "doc-a", [1.0, 0.0, 0.0]) for i in range(5)])
    store.upsert_records(
        [_record(f"t{i}", "doc-b", [1.0, 0.0]) for i in range(2)],
        strict_dimension=False,  # 模拟历史脏数据入库
    )
    store.upsert_records(
        [_record("x1", "doc-c", [0.0, 0.0, 0.0, 0.0, 1.0])],
        strict_dimension=False,
    )
    assert store.get_existing_dimension() == 3


def test_existing_dimension_tie_prefers_latest(store):
    store.upsert_records([
        _record("a1", "doc-a", [1.0, 0.0]),
        _record("b1", "doc-b", [0.0, 1.0, 0.0]),
        _record("a2", "doc-a", [0.0, 1.0]),
        _record("b2", "doc-b", [1.0, 1.0, 0.0]),
    ], strict_dimension=False)
    assert store.get_existing_dimension() == 3  # 并列时取最近写入的维度


def test_existing_dimension_ignores_empty_vectors(store):
    # 空向量行（dimension=0）数量再多也不得参与表决
    store.upsert_records([_record(f"e{i}", "doc-a", []) for i in range(5)])
    store.upsert_records([_record("r1", "doc-a", [1.0, 0.0, 0.0, 0.0])])
    assert store.get_existing_dimension() == 4


def test_upsert_rejects_mixed_dimension(store):
    store.upsert_records([_record("r1", "doc-a", [1.0, 0.0, 0.0])])
    with pytest.raises(ValueError, match="异构维度"):
        store.upsert_records([_record("r2", "doc-a", [1.0, 0.0, 0.0, 0.0])])
    # 空向量行不受守卫影响
    store.upsert_records([_record("r3", "doc-a", [])])
    # 逃生口：整库换维迁移显式关闭守卫
    store.upsert_records([_record("r4", "doc-a", [1.0, 0.0, 0.0, 0.0])], strict_dimension=False)
