"""普通内容问答执行器。"""
from typing import Any, Dict, List

from docs_core.executors.contracts import ExecutorResult
from docs_core.knowledge_service import KnowledgeNode
from docs_core.query.contracts import KnowledgeQueryRequest, RetrievedItem
from docs_core.retrieval.dense_retriever import dense_retriever
from docs_core.retrieval.hybrid_retriever import fuse_candidates, is_toc_candidate
from docs_core.retrieval.reranker import has_sufficient_evidence, rerank_candidates
from docs_core.retrieval.sparse_retriever import sparse_retriever


# 统计候选命中来源与实体类型，便于调试召回质量。
def summarize_candidates(candidates: List[RetrievedItem]) -> Dict[str, Any]:
    by_strategy: Dict[str, int] = {}
    by_entity_type: Dict[str, int] = {}
    by_chunk_type: Dict[str, int] = {}
    by_source_kind: Dict[str, int] = {}
    by_doc_id: Dict[str, int] = {}
    for item in candidates:
        strategy = str(item.metadata.get("strategy") or "unknown")
        entity_type = str(item.entity_type or "unknown")
        chunk_type = str(item.metadata.get("chunk_type") or "")
        source_kind = str(item.metadata.get("source_kind") or "unknown")
        by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
        by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + 1
        if chunk_type:
            by_chunk_type[chunk_type] = by_chunk_type.get(chunk_type, 0) + 1
        by_source_kind[source_kind] = by_source_kind.get(source_kind, 0) + 1
        by_doc_id[item.doc_id] = by_doc_id.get(item.doc_id, 0) + 1
    return {
        "by_strategy": by_strategy,
        "by_entity_type": by_entity_type,
        "by_chunk_type": by_chunk_type,
        "by_source_kind": by_source_kind,
        "by_doc_id": by_doc_id,
    }


# 按目录/正文拆分候选来源，便于在融合层做任务级差异处理。
def split_toc_candidates(candidates: List[RetrievedItem]) -> tuple[List[RetrievedItem], List[RetrievedItem]]:
    toc_candidates: List[RetrievedItem] = []
    content_candidates: List[RetrievedItem] = []
    for item in candidates:
        next_item = item.model_copy(deep=True)
        if is_toc_candidate(next_item):
            next_item.metadata["is_toc"] = True
            toc_candidates.append(next_item)
        else:
            next_item.metadata["is_toc"] = False
            content_candidates.append(next_item)
    return content_candidates, toc_candidates


class ContentExecutor:
    """组织普通问答链的召回、融合与重排。"""

    # 执行通用 dense+sparse 混合召回。
    def retrieve_content_candidates(
        self,
        request: KnowledgeQueryRequest,
        doc_nodes: List[KnowledgeNode],
        task_type: str,
    ) -> tuple[List[RetrievedItem], Dict[str, Any], List[RetrievedItem], List[RetrievedItem]]:
        dense_candidates = dense_retriever.retrieve(request, doc_nodes, task_type)
        sparse_candidates = sparse_retriever.retrieve(request, doc_nodes, task_type)
        dense_content_candidates, dense_toc_candidates = split_toc_candidates(dense_candidates)
        sparse_content_candidates, sparse_toc_candidates = split_toc_candidates(sparse_candidates)
        ranked_candidates, fusion_debug = fuse_candidates(
            {
                "canonical_dense": dense_content_candidates,
                "canonical_sparse": sparse_content_candidates,
                "toc_dense": dense_toc_candidates,
                "toc_sparse": sparse_toc_candidates,
            },
            task_type=task_type,
            top_k=request.top_k,
            filters=request.filters,
        )
        return ranked_candidates, fusion_debug, dense_candidates, sparse_candidates

    # 对候选执行 rerank 与证据充分性过滤。
    def finalize_candidates(
        self,
        query: str,
        task_type: str,
        ranked_candidates: List[RetrievedItem],
        retrieval_route: str,
        *,
        fallback_used: bool = False,
        fusion_debug: Dict[str, Any] | None = None,
        dense_candidates: List[RetrievedItem] | None = None,
        sparse_candidates: List[RetrievedItem] | None = None,
    ) -> ExecutorResult:
        pre_filter_candidates = list(ranked_candidates)
        reranked_candidates = rerank_candidates(query, task_type, ranked_candidates)
        evidence_sufficient = has_sufficient_evidence(query, reranked_candidates)
        if not evidence_sufficient:
            reranked_candidates = []
        return ExecutorResult(
            candidates=reranked_candidates,
            pre_filter_candidates=pre_filter_candidates,
            dense_candidates=list(dense_candidates or []),
            sparse_candidates=list(sparse_candidates or []),
            fusion_debug=fusion_debug or {},
            retrieval_route=retrieval_route,
            fallback_used=fallback_used,
            evidence_sufficient=evidence_sufficient,
        )

    # 组织普通内容问答的执行流程。
    def execute(
        self,
        request: KnowledgeQueryRequest,
        doc_nodes: List[KnowledgeNode],
        task_type: str,
    ) -> ExecutorResult:
        ranked_candidates, fusion_debug, dense_candidates, sparse_candidates = self.retrieve_content_candidates(
            request,
            doc_nodes,
            task_type,
        )
        return self.finalize_candidates(
            request.query,
            task_type,
            ranked_candidates,
            "content_hybrid",
            fusion_debug=fusion_debug,
            dense_candidates=dense_candidates,
            sparse_candidates=sparse_candidates,
        )
