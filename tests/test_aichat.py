"""
AIChat 功能测试
测试流式对话、上下文管理、模型配置等功能
"""
import pytest
import json
import time
from typing import Generator

# 测试配置
TEST_MODEL = "Qwen2.5-7B (SiliconFlow)"


class TestAIChatAPI:
    """测试 AI Chat API 接口"""

    def test_chat_stream_endpoint(self, client):
        """测试流式对话接口"""
        request_data = {
            "message": "你好，请介绍一下自己",
            "history": [],
            "model": TEST_MODEL,
            "mode": "chat"
        }

        response = client.post(
            "/api/chat",
            json=request_data,
            headers={"Accept": "text/event-stream"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # 解析 SSE 响应
        events = []
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    events.append(event)
                except json.JSONDecodeError:
                    continue

        # 验证事件序列
        assert len(events) >= 2
        assert events[0]["type"] == "start"
        assert events[0]["messageId"] is not None

        # 验证有 chunk 事件
        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) > 0

        # 验证结束事件
        end_events = [e for e in events if e["type"] == "end"]
        assert len(end_events) == 1
        assert "usage" in end_events[0]

    def test_chat_with_history(self, client):
        """测试带历史上下文的对话"""
        request_data = {
            "message": "刚才我说了什么？",
            "history": [
                {"role": "user", "content": "我喜欢蓝色"},
                {"role": "assistant", "content": "好的，我记住了你喜欢蓝色。"}
            ],
            "model": TEST_MODEL,
            "mode": "chat"
        }

        response = client.post("/api/chat", json=request_data)
        assert response.status_code == 200

        # 验证响应包含历史上下文
        content = ""
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    if event.get("type") == "chunk":
                        content += event.get("content", "")
                except json.JSONDecodeError:
                    continue

        # 助手应该能回忆起用户喜欢蓝色
        assert "蓝色" in content or "喜欢" in content

    def test_chat_invalid_model(self, client):
        """测试无效模型配置"""
        request_data = {
            "message": "测试消息",
            "history": [],
            "model": "InvalidModel",
            "mode": "chat"
        }

        response = client.post("/api/chat", json=request_data)
        assert response.status_code == 200  # 流式响应返回 200

        # 检查错误事件
        has_error = False
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                try:
                    event = json.loads(data)
                    if event.get("type") == "error":
                        has_error = True
                        break
                except json.JSONDecodeError:
                    continue

        assert has_error

    def test_chat_empty_message(self, client):
        """测试空消息处理"""
        request_data = {
            "message": "",
            "history": [],
            "model": TEST_MODEL
        }

        response = client.post("/api/chat", json=request_data)
        # 空消息应该返回错误或空响应
        assert response.status_code in [200, 400]


class TestContextManagement:
    """测试上下文管理功能"""

    def test_context_window_sliding(self, client):
        """测试上下文滑动窗口"""
        # 构建超过 10 轮的历史
        history = []
        for i in range(15):
            history.append({"role": "user", "content": f"这是第{i+1}轮问题"})
            history.append({"role": "assistant", "content": f"这是第{i+1}轮回答"})

        request_data = {
            "message": "请告诉我这是第几轮对话？",
            "history": history,
            "model": TEST_MODEL
        }

        response = client.post("/api/chat", json=request_data)
        assert response.status_code == 200

    def test_context_compression(self, client):
        """测试上下文压缩"""
        # 构建长文本历史
        long_text = "这是一段很长的文本。" * 1000  # 约 17000 字符
        history = [
            {"role": "user", "content": long_text},
            {"role": "assistant", "content": "我已经收到了你的长文本。"}
        ]

        request_data = {
            "message": "总结一下刚才的内容",
            "history": history,
            "model": TEST_MODEL
        }

        response = client.post("/api/chat", json=request_data)
        assert response.status_code == 200


class TestModelConfiguration:
    """测试模型配置功能"""

    def test_llm_configs_endpoint(self, client):
        """测试获取模型配置接口"""
        response = client.get("/api/llm_configs")
        assert response.status_code == 200

        configs = response.json()
        assert isinstance(configs, list)
        assert len(configs) > 0

        # 验证配置格式
        for config in configs:
            assert "name" in config
            assert "model" in config
            assert "configured" in config
            assert isinstance(config["configured"], bool)

    def test_default_model_priority(self, client):
        """测试默认模型优先级（Qwen2.5-7B 优先）"""
        response = client.get("/api/llm_configs")
        configs = response.json()

        if len(configs) > 1:
            # 第一个模型应该是 Qwen2.5-7B
            first_model = configs[0]["name"]
            assert "Qwen2.5-7B" in first_model or "qwen2.5-7b" in first_model.lower()


class TestStreamResponse:
    """测试流式响应功能"""

    def test_stream_content_type(self, client):
        """测试流式响应 Content-Type"""
        request_data = {
            "message": "你好",
            "history": [],
            "model": TEST_MODEL
        }

        response = client.post("/api/chat", json=request_data)

        # 验证响应头
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("connection") == "keep-alive"

    def test_stream_event_format(self, client):
        """测试 SSE 事件格式"""
        request_data = {
            "message": "你好",
            "history": [],
            "model": TEST_MODEL
        }

        response = client.post("/api/chat", json=request_data)

        event_types = set()
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    event_types.add(event.get("type"))
                except json.JSONDecodeError:
                    continue

        # 验证事件类型
        assert "start" in event_types
        assert "chunk" in event_types
        assert "end" in event_types

    def test_stream_performance(self, client):
        """测试流式响应性能"""
        request_data = {
            "message": "请写一段 100 字左右的自我介绍",
            "history": [],
            "model": TEST_MODEL
        }

        start_time = time.time()
        response = client.post("/api/chat", json=request_data)

        # 读取所有事件
        chunk_count = 0
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                    if event.get("type") == "chunk":
                        chunk_count += 1
                except json.JSONDecodeError:
                    continue

        elapsed = time.time() - start_time

        # 验证性能指标
        assert chunk_count > 5  # 应该有多个 chunk
        assert elapsed < 30  # 总时间应该小于 30 秒


class TestMultimodalReserve:
    """测试多模态预留接口"""

    def test_chat_request_with_images(self, client):
        """测试带图片的请求格式（预留）"""
        request_data = {
            "message": "描述这张图片",
            "history": [],
            "model": TEST_MODEL,
            "mode": "vision",
            "context": {
                "references": ["doc-1", "doc-2"]
            }
        }

        # 目前应该能正常处理（忽略多模态字段）
        response = client.post("/api/chat", json=request_data)
        assert response.status_code == 200


# 模拟测试（不需要真实 API 调用）
class TestAIChatMock:
    """AIChat 单元测试（模拟）"""

    def test_estimate_tokens(self):
        """测试 token 估算函数"""
        from apps.web_console.src.stores.chat import estimateTokens

        # 英文
        msg_en = {"role": "user", "content": "Hello world", "timestamp": 0}
        tokens_en = estimateTokens(msg_en)
        assert tokens_en == 6  # 11 字符 * 0.5 = 5.5 → 6

        # 中文
        msg_zh = {"role": "user", "content": "你好世界", "timestamp": 0}
        tokens_zh = estimateTokens(msg_zh)
        assert tokens_zh == 6  # 4 字符 * 1.5 = 6

    def test_manage_context_sliding_window(self):
        """测试上下文滑动窗口"""
        from apps.web_console.src.stores.chat import manageContext

        # 构建 20 轮对话
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"问题{i+1}", "timestamp": 0})
            messages.append({"role": "assistant", "content": f"回答{i+1}", "timestamp": 0})

        # 应用上下文管理
        managed = manageContext(messages, {"maxRounds": 10, "enableCompression": False, "compressionThreshold": 4000})

        # 验证只保留最近 10 轮
        user_messages = [m for m in managed if m["role"] == "user"]
        assert len(user_messages) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
