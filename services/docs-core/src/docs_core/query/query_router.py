"""知识查询路由兼容导出。"""

from docs_core.query.contracts import TaskType
from docs_core.query.intent_parser import (
    ROUTE_KEYWORDS,
    extract_inline_clause_refs,
    looks_like_table_query,
    normalize_query,
    parse_intent,
)


# 兼容旧路由函数名，内部转发到新的意图解析器。
def route_query(query: str, mode: str = "auto") -> TaskType:
    return parse_intent(query, mode)
