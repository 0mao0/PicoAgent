"""融合 dense 与 sparse 候选的 hybrid 检索器。"""
from typing import Any, Dict, List, Tuple

from docs_core.query.contracts import KnowledgeQueryFilter, RetrievedItem


# 对单个来源内的候选分数做归一化。
def normalize_candidate_scores(candidates: List[RetrievedItem]) -> List[RetrievedItem]:
    if not candidates:
        return []
    max_score = max(item.score for item in candidates) or 1.0
    normalized: List[RetrievedItem] = []
    for item in candidates:
        next_item = item.model_copy(deep=True)
        next_item.metadata["raw_score"] = item.score
        next_item.metadata["normalized_score"] = round(item.score / max_score, 6)
        normalized.append(next_item)
    return normalized


# 为不同来源分配第一版融合权重。
def get_source_weight(source_kind: str) -> float:
    source_weights = {
        "canonical_dense": 1.15,
        "canonical_sparse": 1.20,
    }
    return source_weights.get(source_kind, 1.0)


# 按任务类型给候选加轻量业务权重。
def get_task_type_bonus(task_type: str, item: RetrievedItem) -> float:
    chunk_type = str(item.metadata.get("chunk_type") or "")
    if task_type == "table_qa" and chunk_type.startswith("table_"):
        return 0.25
    if task_type == "locate_qa" and chunk_type in {"outline_anchor", "title"}:
        return 0.20
    if task_type == "definition_qa" and chunk_type in {"content", "schema_desc"}:
        return 0.10
    return 0.0


# 构造候选去重键。
def build_candidate_key(item: RetrievedItem) -> str:
    return item.item_id or f"{item.doc_id}:{item.entity_type}:{item.title}"


# 应用 metadata filter，控制 section 与页码范围。
def apply_metadata_filter(candidates: List[RetrievedItem], filters: KnowledgeQueryFilter | None) -> List[RetrievedItem]:
    if filters is None:
        return candidates
    filtered: List[RetrievedItem] = []
    for item in candidates:
        page_idx = int(item.metadata.get("page_idx", 0) or 0)
        section_path = str(item.metadata.get("section_path", "") or "")
        if filters.section_path and filters.section_path not in section_path:
            continue
        if filters.page_start is not None and page_idx < filters.page_start:
            continue
        if filters.page_end is not None and page_idx > filters.page_end:
            continue
        filtered.append(item)
    return filtered


# 融合多来源候选并输出最终排序结果。
def fuse_candidates(
    source_candidates: Dict[str, List[RetrievedItem]],
    task_type: str,
    top_k: int,
    filters: KnowledgeQueryFilter | None = None,
) -> Tuple[List[RetrievedItem], Dict[str, Any]]:
    fused: Dict[str, RetrievedItem] = {}
    source_debug: Dict[str, Any] = {}

    for source_kind, candidates in source_candidates.items():
        normalized = normalize_candidate_scores(candidates)
        source_weight = get_source_weight(source_kind)
        source_debug[source_kind] = {
            "input_hits": len(candidates),
            "weight": source_weight,
        }
        for item in normalized:
            normalized_score = float(item.metadata.get("normalized_score") or 0.0)
            fusion_score = normalized_score * source_weight + get_task_type_bonus(task_type, item)
            key = build_candidate_key(item)
            existing = fused.get(key)
            if existing is None:
                next_item = item.model_copy(deep=True)
                next_item.rerank_score = round(fusion_score, 6)
                next_item.metadata["fusion_score"] = round(fusion_score, 6)
                next_item.metadata["fusion_sources"] = [source_kind]
                fused[key] = next_item
                continue

            existing_score = float(existing.rerank_score or 0.0)
            merged_score = 1 - (1 - min(existing_score, 0.999999)) * (1 - min(fusion_score, 0.999999))
            existing.rerank_score = round(merged_score, 6)
            existing.metadata["fusion_score"] = round(merged_score, 6)
            existing.metadata.setdefault("fusion_sources", [])
            if source_kind not in existing.metadata["fusion_sources"]:
                existing.metadata["fusion_sources"].append(source_kind)
            if fusion_score > existing_score:
                existing.score = item.score
                existing.title = item.title
                existing.text = item.text
                existing.entity_type = item.entity_type
                existing.metadata.update(item.metadata)
                existing.metadata["fusion_score"] = round(merged_score, 6)
                existing.metadata["fusion_sources"] = list(dict.fromkeys(existing.metadata.get("fusion_sources", [])))

    filtered = apply_metadata_filter(list(fused.values()), filters)
    ranked = sorted(
        filtered,
        key=lambda item: (
            float(item.rerank_score or 0.0),
            float(item.metadata.get("normalized_score") or 0.0),
            -len(item.text),
        ),
        reverse=True,
    )
    limit = max(1, min(20, top_k))
    return ranked[:limit], {
        "sources": source_debug,
        "deduped_hits": len(fused),
        "filtered_hits": len(filtered),
        "returned_hits": min(len(ranked), limit),
    }

