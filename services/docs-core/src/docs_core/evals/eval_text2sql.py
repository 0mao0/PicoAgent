"""Text-to-SQL 评测模块。"""
import json
from pathlib import Path
from typing import Any, Dict, List

from docs_core.query.contracts import KnowledgeQueryRequest
from docs_core.query.service import knowledge_query_service


# 解析 docs-core 评测样本目录。
def resolve_eval_data_dir() -> Path:
    current_file = Path(__file__).resolve()
    return current_file.parents[5] / "tests" / "evals" / "knowledge_rag"


# 读取 jsonl 文件中的全部记录。
def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    if not file_path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


# 调用当前知识查询服务，获取 SQL 结果。
def run_predictions(sql_questions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    predictions: Dict[str, Dict[str, Any]] = {}
    for question in sql_questions:
        question_id = str(question.get("question_id") or "")
        query = str(question.get("question") or "").strip()
        if not question_id or not query:
            continue
        request = KnowledgeQueryRequest(
            query=query,
            library_id=str(question.get("library_id") or "default"),
            doc_ids=list(question.get("doc_ids") or []),
            mode="sql",
            top_k=5,
            include_debug=True,
        )
        response = knowledge_query_service.query(request)
        predictions[question_id] = {
            "query_id": response.query_id,
            "task_type": response.task_type,
            "sql": response.sql.model_dump(mode="json") if response.sql is not None else None,
            "answer": response.answer,
            "debug": response.debug,
        }
    return predictions


# 评估最小 Text-to-SQL 闭环是否返回成功执行结果。
def evaluate_text2sql(
    sql_questions: List[Dict[str, Any]],
    gold_sql: Dict[str, Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    total = 0
    sql_success = 0.0
    sql_match = 0.0
    details: List[Dict[str, Any]] = []
    for question in sql_questions:
        question_id = str(question.get("question_id") or "")
        if not question_id:
            continue
        total += 1
        prediction = predictions.get(question_id, {})
        payload = dict(prediction.get("sql") or {})
        generated_sql = str(payload.get("generated_sql") or "").strip()
        execution_status = str(payload.get("execution_status") or "")
        gold_row = gold_sql.get(question_id, {})
        expected_sql = str(gold_row.get("expected_sql") or "").strip()
        success = 1.0 if execution_status == "success" else 0.0
        match = 1.0 if expected_sql and generated_sql == expected_sql else 0.0
        sql_success += success
        sql_match += match
        details.append(
            {
                "question_id": question_id,
                "task_type": prediction.get("task_type"),
                "execution_status": execution_status,
                "generated_sql": generated_sql,
                "expected_sql": expected_sql,
                "sql_success": success,
                "sql_exact_match": match if expected_sql else None,
                "debug": prediction.get("debug", {}),
            }
        )
    if total == 0:
        return {
            "total": 0,
            "sql_success_rate": 0.0,
            "sql_exact_match_rate": 0.0,
            "details": [],
        }
    exact_match_total = sum(1 for row in gold_sql.values() if row.get("expected_sql"))
    return {
        "total": total,
        "sql_success_rate": round(sql_success / total, 4),
        "sql_exact_match_rate": round(sql_match / exact_match_total, 4) if exact_match_total else 0.0,
        "details": details,
    }


# 脚本入口：读取 SQL 样本并调用当前 Text-to-SQL 主链。
def main() -> None:
    base_dir = resolve_eval_data_dir()
    questions = load_jsonl(base_dir / "questions.jsonl")
    gold_sql_rows = load_jsonl(base_dir / "gold_sql.jsonl")
    gold_sql = {str(row.get("question_id") or ""): row for row in gold_sql_rows if row.get("question_id")}
    sql_question_ids = set(gold_sql.keys())
    sql_questions = [question for question in questions if str(question.get("question_id") or "") in sql_question_ids]
    predictions = run_predictions(sql_questions)
    report = evaluate_text2sql(sql_questions, gold_sql, predictions)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
