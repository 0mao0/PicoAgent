"""reasoning 增量的 delta 事件契约：必须恒带 text 键（思考增量为空串）。

回归 2026-09-06 评测 run 53 题全灭事故：Qwen3.8-Flash 直连端点思考全量输出时，
旧实现把 delta.reasoning 以无 text 键的 delta 事件发出，chat()/chat_stream 等消费方
按 event["text"] 取值 → KeyError('text') → 整次生成判失败。
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SRC = TESTS_DIR.parent / "src"
for p in (str(SRC), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import helpers

from ai_inference.llm_client import LLMClient
from ai_inference.llm_config import LLMClientConfig, LLMModelConfig, RetryConfig


def _client() -> LLMClient:
    model = LLMModelConfig(
        name="thinker", model="model-thinker", api_key="k",
        base_url="https://example.com", enabled=True, priority=10,
    )
    return LLMClient(LLMClientConfig(models=[model], default_model=model.name, retry=RetryConfig(max_retries=0)))


REASONING_STREAM = [
    helpers.make_chunk(reasoning="先想一步"),
    helpers.make_chunk(reasoning="再想一步"),
    helpers.make_chunk("最终答案"),
    helpers.make_chunk(None, finish_reason="stop"),
]


class TestReasoningDeltaContract(unittest.TestCase):
    def test_reasoning_delta_events_always_carry_text_key(self):
        client = _client()
        completions = helpers.FakeCompletions(stream_chunks=list(REASONING_STREAM))
        with mock.patch("ai_inference.llm_client.OpenAI", helpers.make_sync_factory(completions)):
            events = list(client.chat_stream_events([{"role": "user", "content": "hi"}]))
        deltas = [e for e in events if e["type"] == "delta"]
        for e in deltas:
            self.assertIn("text", e)
        # 思考增量带 reasoning 且 text 为空；答案增量带 text
        self.assertEqual([(e["text"], e.get("reasoning")) for e in deltas],
                         [("", "先想一步"), ("", "再想一步"), ("最终答案", None)])

    def test_reasoning_only_stream_aggregates_without_keyerror(self):
        """事故路径：chat_stream_events 内部聚合环（partial_parts）逐事件读 event["text"]，
        纯思考流修复前会以 KeyError('text') 判整次生成失败并换端点。"""
        client = _client()
        chunks = [
            helpers.make_chunk(reasoning="只想不答"),
            helpers.make_chunk(None, finish_reason="stop"),
        ]
        completions = helpers.FakeCompletions(stream_chunks=chunks)
        with mock.patch("ai_inference.llm_client.OpenAI", helpers.make_sync_factory(completions)):
            events = list(client.chat_stream_events([{"role": "user", "content": "hi"}]))
        types = [e["type"] for e in events]
        self.assertEqual(types, ["delta", "done"])
        self.assertNotIn("stream_failed", types)
        self.assertEqual(events[-1].get("used_config"), "thinker")

    def test_chat_stream_yields_answer_text_only(self):
        client = _client()
        completions = helpers.FakeCompletions(stream_chunks=list(REASONING_STREAM))
        with mock.patch("ai_inference.llm_client.OpenAI", helpers.make_sync_factory(completions)):
            yielded = list(client.chat_stream([{"role": "user", "content": "hi"}]))
        self.assertEqual("".join(yielded), "最终答案")


if __name__ == "__main__":
    unittest.main()
