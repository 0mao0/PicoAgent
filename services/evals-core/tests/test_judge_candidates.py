"""run 级判分模型候选链：UI 选定的评价模型排第一，其后接环境候选链兜底（去重）。"""
import json
import os
import sys
import unittest
from pathlib import Path


EVALS_CORE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(EVALS_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(EVALS_CORE_SRC))

from evals_core.runner.answer_eval import _judge_candidates, _resolve_judge_candidates  # noqa: E402


class JudgeCandidateTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in ("EVAL_JUDGE_CONFIGS", "EVAL_JUDGE_MODEL")
        }

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_preferred_judge_first_with_chain_fallback_dedup(self):
        os.environ["EVAL_JUDGE_CONFIGS"] = json.dumps(["judge-a", "judge-b"])
        self.assertEqual(
            _resolve_judge_candidates("judge-b"),
            ["judge-b", "judge-a"],
        )
        # 链外模型置顶，链全体保留兜底
        self.assertEqual(
            _resolve_judge_candidates("judge-x"),
            ["judge-x", "judge-a", "judge-b"],
        )

    def test_no_preferred_equals_env_chain(self):
        os.environ["EVAL_JUDGE_CONFIGS"] = json.dumps(["judge-a", "judge-b"])
        self.assertEqual(_resolve_judge_candidates(None), _judge_candidates())
        self.assertEqual(_resolve_judge_candidates("  "), _judge_candidates())

    def test_default_env_chain_single_and_none(self):
        os.environ.pop("EVAL_JUDGE_CONFIGS", None)
        os.environ["EVAL_JUDGE_MODEL"] = "solo-judge"
        self.assertEqual(_resolve_judge_candidates(None), ["solo-judge"])
        self.assertEqual(_resolve_judge_candidates("other"), ["other", "solo-judge"])
        os.environ.pop("EVAL_JUDGE_MODEL", None)
        self.assertEqual(_resolve_judge_candidates(None), [None])


if __name__ == "__main__":
    unittest.main()
