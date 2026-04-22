"""评测报告聚合模块。"""
import json
from typing import Any, Dict

from docs_core.evals.eval_answer import evaluate_answers, load_jsonl as load_answer_jsonl, run_predictions as run_answer_predictions, resolve_eval_data_dir as resolve_answer_eval_data_dir
from docs_core.evals.eval_retrieval import evaluate_retrieval, load_jsonl as load_retrieval_jsonl, run_predictions as run_retrieval_predictions
from docs_core.evals.eval_text2sql import evaluate_text2sql, run_predictions as run_sql_predictions


# 聚合 retrieval、answer、text2sql 三类评测结果。
def build_eval_suite_report() -> Dict[str, Any]:
    base_dir = resolve_answer_eval_data_dir()
    questions = load_answer_jsonl(base_dir / "questions.jsonl")
    gold_retrieval_rows = load_retrieval_jsonl(base_dir / "gold_retrieval.jsonl")
    gold_answer_rows = load_answer_jsonl(base_dir / "gold_answers.jsonl")
    gold_sql_rows = load_answer_jsonl(base_dir / "gold_sql.jsonl")
    gold_retrieval = {str(row.get("question_id") or ""): row for row in gold_retrieval_rows}
    gold_answers = {str(row.get("question_id") or ""): row for row in gold_answer_rows}
    gold_sql = {str(row.get("question_id") or ""): row for row in gold_sql_rows if row.get("question_id")}
    answer_predictions = run_answer_predictions(questions)
    retrieval_predictions = run_retrieval_predictions(questions)
    sql_question_ids = set(gold_sql.keys())
    sql_questions = [question for question in questions if str(question.get("question_id") or "") in sql_question_ids]
    sql_predictions = run_sql_predictions(sql_questions)
    return {
        "retrieval": evaluate_retrieval(questions, gold_retrieval, retrieval_predictions),
        "answer": evaluate_answers(questions, gold_answers, answer_predictions),
        "text2sql": evaluate_text2sql(sql_questions, gold_sql, sql_predictions),
    }


# 脚本入口：输出统一评测报告。
def main() -> None:
    print(json.dumps(build_eval_suite_report(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
