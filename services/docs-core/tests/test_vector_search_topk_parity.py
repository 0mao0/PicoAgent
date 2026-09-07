"""search() 部分选择优化与「朴素全量参照（旧算法）」的一致性回归。

覆盖点：
- 常规随机 fixture：新路径与「全量打分 + 全量构造 + 排序截断」结果完全一致；
- 并列边界 fixture：多条相同 embedding（点积全等）+ 不同 content 长度，
  验证第 take 名同分行并入池后的破平语义与旧实现一致；
- doc_ids / entity_types 过滤路径一致性；
- top_k 边界（1 / 大于行数 / 0 取 1 / 200 钳位）。
"""
import numpy as np
import pytest

from docs_core.step06_vectors import sqlite_vector_store as svs
from docs_core.step06_vectors.sqlite_vector_store import SQLiteVectorStore
from docs_core.step06_vectors.vector_store import VectorRecord


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """独立临时库 + 隔离的模块级缓存 + 小批次（与 test_vector_store_cache 同款）。"""
    saved_cache = dict(svs._VECTOR_CACHE)
    monkeypatch.setattr(svs, "_CACHE_BUILD_BATCH_SIZE", 2)
    svs._VECTOR_CACHE.update({"loaded_mtime": None, "rows": None, "matrix": None})
    yield SQLiteVectorStore(db_path=tmp_path / "vectors.sqlite")
    svs._VECTOR_CACHE.clear()
    svs._VECTOR_CACHE.update(saved_cache)


def _record(record_id: str, doc_id: str, entity_type: str, embedding, content: str) -> VectorRecord:
    return VectorRecord(
        record_id=record_id,
        doc_id=doc_id,
        entity_type=entity_type,
        entity_id=record_id,
        content=content,
        metadata={"doc_id": doc_id, "entity_type": entity_type, "tag": record_id},
        embedding=embedding,
    )


def _naive_reference(records, query_embedding, top_k):
    """旧算法参照：全量点积 → 全量构造 → (score, len(content)) 降序排序 → 截断。

    与库内实现共用同一 fp32 矩阵与 matmul，保证分数逐位一致，从而并列比较口径相同。
    """
    valid = [rec for rec in records if rec.embedding]
    if not valid:
        return []
    matrix = np.asarray([rec.embedding for rec in valid], dtype=np.float32)
    q = np.asarray(query_embedding, dtype=np.float32)
    scores = (matrix @ q).tolist()
    hits = []
    for rank, rec in enumerate(valid):
        hits.append({
            "record_id": rec.record_id,
            "content": rec.content or "",
            "score": float(scores[rank]),
            "metadata": dict(rec.metadata),
        })
    ranked = sorted(hits, key=lambda item: (float(item["score"]), len(item["content"])), reverse=True)
    cap = max(1, min(200, top_k))
    return ranked[:cap]


def _assert_parity(store, records, query_embedding, *, doc_ids=None, entity_types=None, top_k=20):
    store.upsert_records(records)
    hits = store.search(query_embedding, doc_ids=doc_ids, entity_types=entity_types, top_k=top_k)
    filtered = [
        rec for rec in records
        if rec.embedding
        and (not doc_ids or rec.doc_id in doc_ids)
        and (not entity_types or rec.entity_type in entity_types)
    ]
    expected = _naive_reference(filtered, query_embedding, top_k)
    assert [hit.record_id for hit in hits] == [item["record_id"] for item in expected]
    if expected:
        assert len(hits) == len(expected) == min(max(1, min(200, top_k)), len(expected))
        # 分数与 metadata 也逐位对齐
        assert [round(hit.score, 6) for hit in hits] == [round(item["score"], 6) for item in expected]
        assert [dict(hit.metadata) for hit in hits] == [item["metadata"] for item in expected]


def _random_records(n, dim, rng):
    records = []
    for i in range(n):
        vec = rng.standard_normal(dim).tolist()
        doc = f"doc-{i % 5}"
        etype = "chunk" if i % 3 else "formula"
        records.append(_record(f"rec-{i:04d}", doc, etype, vec, f"内容-{i}-" + "x" * (i % 11)))
    return records


def test_random_fixture_full_parity(store):
    rng = np.random.default_rng(7)
    records = _random_records(130, 8, rng)
    query = rng.standard_normal(8).tolist()
    _assert_parity(store, records, query, top_k=20)
    _assert_parity(store, records, query, top_k=5)


def test_random_fixture_above_cap_200(store):
    rng = np.random.default_rng(11)
    records = _random_records(250, 6, rng)  # 超过 cap=200，走部分选择
    query = rng.standard_normal(6).tolist()
    _assert_parity(store, records, query, top_k=200)
    _assert_parity(store, records, query, top_k=10000)  # 钳位到 200


def test_tie_at_boundary_prefers_longer_content(store):
    """60 条同分（同向量同查询）候选，取 top_k=20：旧语义按 content 长度破平，
    第 take 名同分行必须全部并入池后再排序，不能只留 argpartition 的任意 20 行。"""
    records = []
    for i in range(60):
        length = 100 + (i * 13) % 97  # 13 与 97 互质 → 60 个长度互不相同
        records.append(_record(f"tie-a-{i:03d}", "doc-tie", "chunk", [1.0, 0.0, 0.0], "A" * length))
    for i in range(40):
        records.append(_record(f"tie-b-{i:03d}", "doc-tie", "chunk", [0.5, 0.0, 0.0], "B" * (10 + i)))
    _assert_parity(store, records, [1.0, 0.0, 0.0], top_k=20)
    # 显式断言：前 20 名应全是 A 组（分数 1.0），且按 content 长度降序
    hits = store.search([1.0, 0.0, 0.0], top_k=20)
    assert [hit.record_id for hit in hits] == sorted(
        [f"tie-a-{i:03d}" for i in range(60)],
        key=lambda rid: -(100 + (int(rid[-3:]) * 13) % 97),
    )[:20]


def test_filters_parity(store):
    rng = np.random.default_rng(13)
    records = _random_records(90, 6, rng)
    query = rng.standard_normal(6).tolist()
    _assert_parity(store, records, query, doc_ids=["doc-0", "doc-2"], top_k=10)
    _assert_parity(store, records, query, entity_types=["formula"], top_k=10)
    _assert_parity(store, records, query, doc_ids=["doc-1"], entity_types=["chunk"], top_k=3)


def test_topk_edges(store):
    rng = np.random.default_rng(17)
    records = _random_records(30, 5, rng)
    query = rng.standard_normal(5).tolist()
    _assert_parity(store, records, query, top_k=1)
    _assert_parity(store, records, query, top_k=0)  # 旧语义 max(1, ...) → 1
    _assert_parity(store, records, query, top_k=500)  # top_k > 行数 → 全量


def test_empty_embedding_rows_ignored(store):
    records = _random_records(25, 5, np.random.default_rng(19))
    records.append(_record("empty-1", "doc-e", "chunk", [], "空向量"))
    records.append(_record("empty-2", "doc-e", "chunk", [], "空向量2"))
    _assert_parity(store, records, [0.2, -0.1, 0.4, 0.0, 0.3], top_k=5)
    assert "empty-1" not in [hit.record_id for hit in store.search([1.0, 1.0, 1.0, 1.0, 1.0], top_k=25)]


def test_no_valid_rows_returns_empty(store):
    store.upsert_records([_record("empty-1", "doc-e", "chunk", [], "")])
    assert store.search([1.0, 0.0], top_k=5) == []
