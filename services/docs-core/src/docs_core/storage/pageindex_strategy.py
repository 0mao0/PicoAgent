from typing import Any, Dict, List

from .structured_strategy import build_structured_index_for_doc, query_doc_blocks


# 基于 doc_blocks 构建分页投影。
def _build_page_index_items(doc_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for order_index, block in enumerate(doc_blocks):
        page_idx = int(block.get("page_idx") or 0)
        block_seq = int(block.get("block_seq") or 0)
        derived_level = block.get("derived_title_level")
        plain_text = str(block.get("plain_text") or "").strip()
        if not plain_text:
            continue
        block_type = str(block.get("block_type") or "")
        item_type = "page_heading" if block_type == "title" else "page_segment"
        items.append(
            {
                "id": str(block.get("block_uid") or f"page-{order_index}"),
                "item_type": item_type,
                "title": plain_text if item_type == "page_heading" else f"页段@P{page_idx + 1}B{block_seq}",
                "content": plain_text,
                "meta": {
                    "page_idx": page_idx,
                    "page_no": page_idx + 1,
                    "block_uid": block.get("block_uid"),
                    "block_seq": block_seq,
                    "derived_level": derived_level,
                },
                "order_index": order_index,
            }
        )
    return items


# 基于 doc_blocks 主索引构建 PageIndex 下游投影。
def build_pageindex_for_doc(library_id: str, doc_id: str, strategy: str = 'C_pageindex') -> Dict[str, Any]:
    from docs_core import knowledge_service

    doc_blocks = query_doc_blocks(doc_id, limit=1000)
    if not doc_blocks:
        build_structured_index_for_doc(library_id, doc_id, "A_structured")
        doc_blocks = query_doc_blocks(doc_id, limit=1000)
    if not doc_blocks:
        raise ValueError("文档尚无可用 doc_blocks 数据")

    items = _build_page_index_items(doc_blocks)
    saved_count = knowledge_service.save_document_segments(doc_id, library_id, strategy, items)
    stats = knowledge_service.get_document_segment_stats(doc_id)
    return {'saved_count': saved_count, 'stats': stats}
