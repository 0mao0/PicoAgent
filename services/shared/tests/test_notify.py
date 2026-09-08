"""shared.notify 单元测试。"""
import pytest
from shared.notify import split_webhooks, target_label, validate_webhook_url


class TestSplitWebhooks:
    def test_comma_separated(self):
        assert split_webhooks("url1,url2,url3") == ["url1", "url2", "url3"]

    def test_semicolon_separated(self):
        assert split_webhooks("url1;url2;url3") == ["url1", "url2", "url3"]

    def test_whitespace_separated(self):
        assert split_webhooks("url1 url2 url3") == ["url1", "url2", "url3"]

    def test_mixed_separators(self):
        assert split_webhooks("url1,url2;url3 url4") == ["url1", "url2", "url3", "url4"]

    def test_deduplication(self):
        assert split_webhooks("url1,url1,url2") == ["url1", "url2"]

    def test_empty_string(self):
        assert split_webhooks("") == []

    def test_none(self):
        assert split_webhooks(None) == []

    def test_whitespace_only(self):
        assert split_webhooks("   ") == []


class TestTargetLabel:
    def test_valid_url(self):
        assert target_label("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx") == "https://qyapi.weixin.qq.com"

    def test_invalid_url(self):
        assert target_label("not-a-url") == "<无效地址>"


class TestValidateWebhookUrl:
    def test_private_ip_rejected(self):
        with pytest.raises(ValueError, match="非公网地址"):
            validate_webhook_url("http://192.168.1.1/webhook")

    def test_localhost_rejected(self):
        with pytest.raises(ValueError, match="非公网地址"):
            validate_webhook_url("http://localhost/webhook")

    def test_loopback_rejected(self):
        with pytest.raises(ValueError, match="非公网地址"):
            validate_webhook_url("http://127.0.0.1/webhook")

    def test_invalid_scheme_rejected(self):
        with pytest.raises(ValueError, match="协议不合法"):
            validate_webhook_url("ftp://example.com/webhook")

    def test_missing_hostname_rejected(self):
        with pytest.raises(ValueError, match="缺少主机名"):
            validate_webhook_url("http:///webhook")

    def test_embedded_credentials_rejected(self):
        with pytest.raises(ValueError, match="内嵌凭据"):
            validate_webhook_url("https://user:pass@example.com/webhook")
