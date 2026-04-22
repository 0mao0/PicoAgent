"""知识检索能力导出。"""

from .contracts import KnowledgeQueryRequest, KnowledgeQueryResponse
from .execution_planner import ExecutionPlan, build_execution_plan
from .intent_parser import parse_intent
from .query_router import route_query

__all__ = [
    "ExecutionPlan",
    "KnowledgeQueryRequest",
    "KnowledgeQueryResponse",
    "KnowledgeQueryService",
    "build_execution_plan",
    "knowledge_query_service",
    "parse_intent",
    "route_query",
]


def __getattr__(name: str):
    """按需加载 service，避免 contracts 导入路径上的循环依赖。"""
    if name in {"KnowledgeQueryService", "knowledge_query_service"}:
        from .service import KnowledgeQueryService, knowledge_query_service

        exports = {
            "KnowledgeQueryService": KnowledgeQueryService,
            "knowledge_query_service": knowledge_query_service,
        }
        return exports[name]
    raise AttributeError(name)
