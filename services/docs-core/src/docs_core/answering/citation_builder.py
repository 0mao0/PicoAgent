"""引用构造器。"""
from typing import Dict, List

from docs_core.query.contracts import KnowledgeCitation, RetrievedItem


# 截断文本片段，便于前端显示引用摘要。
def build_snippet(text: str, limit: int = 180) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


# 将候选项转换为统一引用结构。
def build_citations(
    candidates: List[RetrievedItem],
    doc_title_map: Dict[str, str],
) -> List[KnowledgeCitation]:
    citations: List[KnowledgeCitation] = []
    for item in candidates:
        citations.append(
            KnowledgeCitation(
                target_id=item.item_id,
                target_type=item.entity_type,
                doc_id=item.doc_id,
                doc_title=doc_title_map.get(item.doc_id, item.title),
                page_idx=int(item.metadata.get("page_idx", 0) or 0),
                section_path=str(item.metadata.get("section_path", "") or ""),
                snippet=build_snippet(item.text),
                score=item.score,
            )
        )
    return citations
