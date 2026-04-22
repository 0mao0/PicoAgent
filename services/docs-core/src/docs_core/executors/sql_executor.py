"""结构化统计问答执行器。"""
from typing import List

from docs_core.executors.contracts import ExecutorResult
from docs_core.knowledge_service import KnowledgeNode, KnowledgeService, knowledge_service
from docs_core.query.contracts import KnowledgeQueryRequest, SqlPayload
from docs_core.text2sql.schema_linker import link_schema
from docs_core.text2sql.sql_explainer import explain_sql_result
from docs_core.text2sql.sql_executor import execute_sql
from docs_core.text2sql.sql_generator import generate_sql
from docs_core.text2sql.sql_planner import plan_sql
from docs_core.text2sql.sql_validator import validate_sql


class SqlExecutor:
    """组织最小 Text-to-SQL 闭环。"""

    # 初始化 SQL 执行器，复用当前 knowledge service 的索引库路径。
    def __init__(self, knowledge_service_impl: KnowledgeService | None = None) -> None:
        self._knowledge_service = knowledge_service_impl or knowledge_service

    # 执行结构化统计问答的最小 SQL 链路。
    def execute(
        self,
        request: KnowledgeQueryRequest,
        doc_nodes: List[KnowledgeNode],
        task_type: str,
    ) -> ExecutorResult:
        linked_schema = link_schema(request.query, request, doc_nodes)
        plan = plan_sql(linked_schema)
        sql, parameters = generate_sql(plan)
        if not plan.supported:
            explanation = explain_sql_result(plan, {"rows": [], "row_count": 0})
            payload = SqlPayload(
                generated_sql="",
                execution_status="not_supported",
                result_preview={"rows": [], "row_count": 0},
                linked_schema=linked_schema,
                explanation=explanation,
            )
            return ExecutorResult(
                candidates=[],
                retrieval_route="sql_execution",
                sql_payload=payload,
                answer=explanation,
                confidence=0.35,
                extra_debug={
                    "sql_supported": False,
                    "sql_plan_reason": plan.reason,
                },
            )
        sql_valid, validation_reason = validate_sql(sql)
        if not sql_valid:
            payload = SqlPayload(
                generated_sql=sql,
                execution_status="validation_failed",
                result_preview={"rows": [], "row_count": 0},
                linked_schema=linked_schema,
                explanation=f"SQL 校验失败：{validation_reason}",
            )
            return ExecutorResult(
                candidates=[],
                retrieval_route="sql_execution",
                sql_payload=payload,
                answer=payload.explanation,
                confidence=0.2,
                extra_debug={
                    "sql_supported": True,
                    "sql_valid": False,
                    "sql_validation_reason": validation_reason,
                },
            )
        result_preview = execute_sql(sql, parameters, db_path=self._knowledge_service.index_db_path)
        explanation = explain_sql_result(plan, result_preview)
        payload = SqlPayload(
            generated_sql=sql,
            execution_status="success",
            result_preview=result_preview,
            linked_schema=linked_schema,
            explanation=explanation,
        )
        return ExecutorResult(
            candidates=[],
            retrieval_route="sql_execution",
            sql_payload=payload,
            answer=explanation,
            confidence=0.85,
            extra_debug={
                "sql_supported": True,
                "sql_valid": True,
                "sql_plan_metric": plan.metric,
                "sql_parameters": list(parameters),
            },
        )
