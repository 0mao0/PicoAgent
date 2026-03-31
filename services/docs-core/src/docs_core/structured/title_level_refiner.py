"""标题层级 LLM 细化器。"""
import json
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from angineer_core.infra.llm_client import LLMClient


def llm_refine_title_levels(
    title_items: list[dict[str, Any]],
    llm_client: Optional["LLMClient"] = None
) -> tuple[dict[str, tuple[int, float]], str]:
    """用 LLM 细化标题层级并返回状态。"""
    if not llm_client:
        return {}, "not_configured"

    if not title_items:
        return {}, "ok"

    mini_items: list[dict[str, Any]] = []
    for item in title_items:
        mini_items.append({
            "block_uid": item["block_uid"],
            "text": item["plain_text"][:160],
            "rule_level": item.get("rule_level"),
        })

    system_prompt = (
        "你是文档结构分析器。根据标题文本的编号层级判断标题级别(>=1，不限制上限)。"
        "如果是目录项也按编号层级判断。仅返回JSON对象："
        '{"items":[{"block_uid":"...","level":1,"confidence":0.95}]}'
    )
    user_prompt = json.dumps({"items": mini_items}, ensure_ascii=False)

    try:
        result_text = llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )

        result = json.loads(result_text)
        arr = result.get("items") if isinstance(result, dict) else result
        refined: dict[str, tuple[int, float]] = {}

        if isinstance(arr, list):
            for item in arr:
                if not isinstance(item, dict):
                    continue
                uid = item.get("block_uid")
                level = item.get("level")
                conf = item.get("confidence", 0.8)
                if isinstance(uid, str) and isinstance(level, int) and level >= 1:
                    confidence = float(conf) if isinstance(conf, (int, float)) else 0.8
                    confidence = max(0.0, min(1.0, confidence))
                    refined[uid] = (level, confidence)

        if refined:
            return refined, "ok"
        return {}, "empty_result"

    except Exception as error:
        return {}, f"error:{str(error)[:50]}"
