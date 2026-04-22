"""表格问答执行器。"""
from typing import List

from docs_core.executors.content_executor import ContentExecutor
from docs_core.executors.contracts import ExecutorResult
from docs_core.knowledge_service import KnowledgeNode
from docs_core.query.contracts import KnowledgeQueryRequest, RetrievedItem
from docs_core.retrieval.table_retriever import table_retriever


class TableExecutor:
    """组织表格问答链及其回退逻辑。"""

    def __init__(self, content_executor: ContentExecutor | None = None) -> None:
        self._content_executor = content_executor or ContentExecutor()

    # 组织表格问答的执行流程。
    def execute(
        self,
        request: KnowledgeQueryRequest,
        doc_nodes: List[KnowledgeNode],
        task_type: str,
    ) -> ExecutorResult:
        table_candidates = table_retriever.retrieve(request, doc_nodes)
        ranked_candidates: List[RetrievedItem] = table_candidates[: max(1, min(20, request.top_k))]
        if not ranked_candidates:
            fallback_result = self._content_executor.execute(request, doc_nodes, task_type)
            fallback_result.retrieval_route = "content_hybrid_fallback"
            fallback_result.fallback_used = True
            return fallback_result
        fusion_debug = {
            "sources": {
                "table_aware": {
                    "input_hits": len(table_candidates),
                    "weight": 1.0,
                }
            },
            "deduped_hits": len(table_candidates),
            "filtered_hits": len(ranked_candidates),
            "returned_hits": len(ranked_candidates),
        }
        return self._content_executor.finalize_candidates(
            request.query,
            task_type,
            ranked_candidates,
            "table_aware",
            fusion_debug=fusion_debug,
        )
