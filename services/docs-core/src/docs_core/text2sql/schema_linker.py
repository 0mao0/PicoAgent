"""Text-to-SQL 的 schema linking。"""
from typing import Dict, List

from docs_core.knowledge_service import KnowledgeNode
from docs_core.query.contracts import KnowledgeQueryRequest


COUNT_METRIC_CATALOG = {
    "document_count": {
        "markers": ("多少篇文档", "多少个文档", "多少份文档", "多少篇规范", "多少份规范"),
        "table_name": "canonical_documents",
        "description": "统计文档数量",
    },
    "chunk_count": {
        "markers": ("多少个内容块", "多少个片段", "多少个chunk", "多少段内容"),
        "table_name": "canonical_chunks",
        "description": "统计内容片段数量",
    },
    "table_count": {
        "markers": ("多少张数据表", "多少张结构化表", "多少个表单元"),
        "table_name": "canonical_tables",
        "description": "统计结构化表格数量",
    },
    "block_count": {
        "markers": ("多少个块", "多少个block", "多少个原子块"),
        "table_name": "canonical_blocks",
        "description": "统计原子块数量",
    },
    "outline_count": {
        "markers": ("多少个章节", "多少个目录节点", "多少个标题节点"),
        "table_name": "canonical_outlines",
        "description": "统计大纲节点数量",
    },
}


# 解析 Text-to-SQL 的作用域过滤条件。
def resolve_scope_filters(request: KnowledgeQueryRequest, doc_nodes: List[KnowledgeNode]) -> Dict[str, object]:
    return {
        "library_id": request.library_id,
        "doc_ids": [node.id for node in doc_nodes] if doc_nodes else list(request.doc_ids),
    }


# 将自然语言问题映射到当前支持的最小结构化查询对象。
def link_schema(
    query: str,
    request: KnowledgeQueryRequest,
    doc_nodes: List[KnowledgeNode],
) -> Dict[str, object]:
    normalized_query = " ".join((query or "").strip().lower().split())
    filters = resolve_scope_filters(request, doc_nodes)
    for metric_name, metric_spec in COUNT_METRIC_CATALOG.items():
        markers = metric_spec["markers"]
        if any(marker in normalized_query for marker in markers):
            return {
                "supported": True,
                "metric": metric_name,
                "table_name": metric_spec["table_name"],
                "description": metric_spec["description"],
                "filters": filters,
            }
    if "多少" in normalized_query or "统计" in normalized_query or "汇总" in normalized_query:
        return {
            "supported": False,
            "metric": "unsupported_analytic_sql",
            "table_name": "",
            "description": "当前只支持对象计数类的最小 Text-to-SQL 闭环。",
            "filters": filters,
            "reason": "unsupported_aggregation_pattern",
        }
    return {
        "supported": False,
        "metric": "unsupported_analytic_sql",
        "table_name": "",
        "description": "当前问题不属于最小 Text-to-SQL 支持范围。",
        "filters": filters,
        "reason": "not_analytic_sql",
    }
