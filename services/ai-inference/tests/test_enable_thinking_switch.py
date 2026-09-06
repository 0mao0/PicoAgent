"""端点级 enable_thinking 开关（LLM_CONFIGS 字段）：显式 > 环境变量 > 隐式 URL/模型名规则。

背景：隐式规则只认 dashscope/aliyun、angineer.cn、模型名含 qwen3.6，直连 vLLM/DGX 的
思考模型一条都不命中 → 思考全量输出（53 题全灭事故触发面）。直连端点现可显式声明
"enable_thinking": true/false。
"""

import os
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


def _client(model_cfg: LLMModelConfig) -> LLMClient:
    return LLMClient(LLMClientConfig(
        models=[model_cfg], default_model=model_cfg.name, retry=RetryConfig(max_retries=0),
    ))


def _extra_body_for(model_cfg: LLMModelConfig, env=None):
    client = _client(model_cfg)
    completions = helpers.FakeCompletions()
    with mock.patch("ai_inference.llm_client.OpenAI", helpers.make_sync_factory(completions)):
        if env is not None:
            with mock.patch.dict(os.environ, {"ANGINEER_CHAT_TEMPLATE_KWARGS": env}):
                client.chat([{"role": "user", "content": "hi"}])
        else:
            with mock.patch.dict(os.environ, {"ANGINEER_CHAT_TEMPLATE_KWARGS": ""}, clear=False):
                os.environ.pop("ANGINEER_CHAT_TEMPLATE_KWARGS", None)
                client.chat([{"role": "user", "content": "hi"}])
    return completions.calls[-1].get("extra_body")


def _cfg(**kw) -> LLMModelConfig:
    base = dict(name="m", model="m-model", api_key="k", base_url="https://dgx-direct.cccc/v1", enabled=True, priority=10)
    base.update(kw)
    return LLMModelConfig(**base)


class TestExplicitSwitch(unittest.TestCase):
    def test_explicit_false_on_direct_endpoint(self):
        body = _extra_body_for(_cfg(enable_thinking=False))
        self.assertEqual(body, {"chat_template_kwargs": {"enable_thinking": False}})

    def test_explicit_true_overrides_implicit_dashscope_rule(self):
        # dashscope 隐式规则会发顶层 enable_thinking:False——显式 True 必须压过它
        body = _extra_body_for(_cfg(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", enable_thinking=True))
        self.assertEqual(body, {"chat_template_kwargs": {"enable_thinking": True}})

    def test_explicit_overrides_env_kwargs(self):
        body = _extra_body_for(_cfg(enable_thinking=True), env='{"other": 1}')
        self.assertEqual(body, {"chat_template_kwargs": {"enable_thinking": True}})


class TestBackwardCompat(unittest.TestCase):
    def test_none_keeps_implicit_angineer_rule(self):
        body = _extra_body_for(_cfg(base_url="https://angineer.cn/api/llm", enable_thinking=None))
        self.assertEqual(body, {"chat_template_kwargs": {"enable_thinking": False}})

    def test_none_direct_endpoint_sends_nothing(self):
        # 未声明时行为与旧版一致：直连不发任何 thinking 相关参数
        body = _extra_body_for(_cfg())
        self.assertIn(body, (None, {}))

    def test_none_honors_env_kwargs(self):
        body = _extra_body_for(_cfg(), env='{"enable_thinking": false}')
        self.assertEqual(body, {"chat_template_kwargs": {"enable_thinking": False}})


if __name__ == "__main__":
    unittest.main()
