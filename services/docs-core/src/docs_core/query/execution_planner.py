"""知识查询执行规划。"""
from dataclasses import dataclass

from docs_core.query.contracts import TaskType


@dataclass(frozen=True)
class ExecutionPlan:
    """查询执行计划。"""

    task_type: TaskType
    executor_name: str
    strategy: str = "canonical_hybrid_v1"


# 判断问题是否偏向公式或计算说明。
def looks_like_formula_query(query: str, task_type: TaskType) -> bool:
    if task_type == "table_qa":
        return False
    markers = ("公式", "按式", "式中", "怎么算", "怎么计算", "如何计算", "计算方法", "按什么计算")
    return any(marker in (query or "") for marker in markers)


# 基于任务类型与问题特征规划本次查询执行链。
def build_execution_plan(query: str, task_type: TaskType) -> ExecutionPlan:
    if task_type == "analytic_sql":
        return ExecutionPlan(task_type=task_type, executor_name="sql", strategy="text2sql_canonical_v1")
    if task_type == "table_qa":
        return ExecutionPlan(task_type=task_type, executor_name="table", strategy="canonical_hybrid_v1")
    if looks_like_formula_query(query, task_type):
        return ExecutionPlan(task_type=task_type, executor_name="formula", strategy="canonical_hybrid_v1")
    return ExecutionPlan(task_type=task_type, executor_name="content", strategy="canonical_hybrid_v1")
