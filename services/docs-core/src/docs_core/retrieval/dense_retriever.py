"""基于 canonical SQLite 的第一版 dense 检索器。"""
import re
from typing import Iterable, List

from docs_core.knowledge_service import KnowledgeNode, knowledge_service
from docs_core.query.contracts import KnowledgeQueryRequest, RetrievedItem
from docs_core.retrieval.query_normalizer import contains_clause_ref, extract_clause_refs, tokenize_query


# 基于关键词重叠计算简单相关分数。
def score_text(query_tokens: Iterable[str], title: str, content: str) -> float:
    score = 0.0
    haystack = f"{title}\n{content}".lower()
    for token in query_tokens:
        if re.fullmatch(r"\d+", token or ""):
            continue
        if token and token in haystack:
            score += 1.0
    return score


class DenseRetriever:
    """从 canonical chunks 中召回语义相关候选。"""

    def retrieve(
        self,
        request: KnowledgeQueryRequest,
        doc_nodes: List[KnowledgeNode],
        task_type: str,
    ) -> List[RetrievedItem]:
        query_tokens = tokenize_query(request.query)
        clause_refs = extract_clause_refs(request.query)
        is_calc_query = any(marker in (request.query or "") for marker in ("怎么计算", "如何计算", "计算方法", "按什么计算", "按式", "公式"))
        candidates: List[RetrievedItem] = []
        for node in doc_nodes:
            chunks = knowledge_service.list_canonical_chunks(
                doc_id=node.id,
                keyword=None,
                limit=max(50, request.top_k * 12),
            )
            for chunk in chunks:
                score = score_text(query_tokens, chunk.section_path, chunk.text)
                if clause_refs and any(contains_clause_ref(f"{chunk.section_path}\n{chunk.text}", ref) for ref in clause_refs):
                    score += 10.0
                if is_calc_query and any(marker in chunk.text for marker in ("按式", "公式", "式中", "计算")):
                    score += 4.0
                if score <= 0:
                    continue
                if task_type == "table_qa" and chunk.chunk_type.startswith("table_"):
                    score += 2.0
                if task_type == "definition_qa" and chunk.chunk_type in {"outline_anchor", "table_summary"}:
                    score += 1.2
                if task_type == "locate_qa" and chunk.chunk_type == "outline_anchor":
                    score += 1.5
                candidates.append(
                    RetrievedItem(
                        item_id=chunk.chunk_id,
                        entity_type=chunk.chunk_type,
                        doc_id=node.id,
                        title=chunk.section_path or node.title,
                        text=chunk.text,
                        score=score * 1.1,
                        metadata={
                            "page_idx": chunk.page_start,
                            "section_path": chunk.section_path,
                            "source_kind": "canonical_dense",
                            "chunk_type": chunk.chunk_type,
                            "strategy": "canonical_dense_v1",
                            "source_block_ids": list(chunk.source_block_ids),
                        },
                    )
                )
        return candidates


dense_retriever = DenseRetriever()
