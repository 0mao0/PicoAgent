"""meta_query 路由与回退守卫：
1) 关键词快速通道只收真正的统计问法，枚举/列举/定位型内容题不得进统计通道；
2) 统计通道拒答话术（统计维度暂不支持/仅负责元数据…）必须被判为不可用，触发 L1 回退。
背景：库里有哪些规范/第二篇文章是什么 被误路由进统计通道后，用户拿到固定拒答话术。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/angineer-core/src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../services/ai-inference/src")))

from angineer_core.classifier import _is_meta_query  # noqa: E402
from angineer_core.agent_policy import _meta_answer_usable  # noqa: E402
from angineer_core.agent_messages import AgentMessage  # noqa: E402

META_REFUSAL = (
    "抱歉，统计维度暂不支持。本助手仅负责回答知识库的元数据问题"
    "（如文档数量、状态分布、存储占用等），无法提供具体文档的标题或正文内容。"
)


class MetaQueryFastPathTests(unittest.TestCase):
    def test_pure_count_queries_stay_meta(self):
        # 真统计问法必须保留快速通道（回归保护）
        for query in ("库里有多少文章", "库里有几个文档", "知识库文档数量分布", "库里几篇文章，处理状态如何"):
            self.assertTrue(_is_meta_query(query), query)

    def test_enumeration_and_listing_queries_are_not_meta(self):
        for query in (
            "库里有哪些规范",
            "库里有哪些文章",
            "第二篇文章是什么",
            "列出知识库里的文档标题",
            "知识库收录的资料名称有哪些",
            "第一篇文档讲了什么",
        ):
            self.assertFalse(_is_meta_query(query), query)


class MetaAnswerUsableGuardTests(unittest.TestCase):
    def test_stats_channel_refusal_is_unusable_and_triggers_fallback(self):
        messages = [AgentMessage(role="assistant", content=META_REFUSAL)]
        self.assertFalse(_meta_answer_usable(messages))

    def test_real_stats_answer_is_usable(self):
        messages = [AgentMessage(role="assistant", content="当前知识库共有 26 篇文章，其中 24 篇为 PDF 格式。")]
        self.assertTrue(_meta_answer_usable(messages))


if __name__ == "__main__":
    unittest.main()
