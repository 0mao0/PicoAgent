"""notify.send 加固回归：多群拆分 / SSRF 边界 / errcode 拒收（凭据绝不入测试，全部用假地址）。"""
import json

import pytest

from shared import notify


def _fake_addrinfo(ip):
    def _get(host, port):
        return [(2, 1, 6, "", (ip, port))]
    return _get


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_split_webhooks_dedupe_order():
    raw = "https://a.example/x, https://b.example/x;https://a.example/x\nhttps://c.example/x"
    assert notify.split_webhooks(raw) == [
        "https://a.example/x", "https://b.example/x", "https://c.example/x"]
    assert notify.split_webhooks("") == []


def test_target_label_masks_key():
    label = notify.target_label("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SECRET")
    assert label == "https://qyapi.weixin.qq.com"
    assert "SECRET" not in label


def _host_token(url):
    host = url.split("//", 1)[1].split("/", 1)[0]
    if host.startswith("["):
        return host[1:host.index("]")]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


@pytest.mark.parametrize("url,ip", [
    ("http://localhost:8080/hook", "127.0.0.1"),
    ("http://127.0.0.1/hook", "127.0.0.1"),
    ("http://10.0.0.5/hook", "10.0.0.5"),
    ("http://172.16.9.9/hook", "172.16.9.9"),
    ("http://192.168.1.1/hook", "192.168.1.1"),
    ("http://169.254.1.1/hook", "169.254.1.1"),
    ("http://[::1]/hook", "::1"),
])
def test_validate_rejects_non_public(monkeypatch, url, ip):
    assert _host_token(url)  # 主机名解析自检
    monkeypatch.setattr(notify.socket, "getaddrinfo", _fake_addrinfo(ip))
    with pytest.raises(ValueError):
        notify.validate_webhook_url(url)


@pytest.mark.parametrize("url", [
    "ftp://qyapi.example/hook",
    "file:///etc/passwd",
    "https://user:pass@qyapi.example/hook",
])
def test_validate_rejects_scheme_and_embedded_credential(url):
    with pytest.raises(ValueError):
        notify.validate_webhook_url(url)


def test_validate_accepts_public(monkeypatch):
    monkeypatch.setattr(notify.socket, "getaddrinfo", _fake_addrinfo("103.7.28.161"))
    notify.validate_webhook_url("https://qyapi.example/cgi-bin/webhook/send?key=x")


def test_send_rejects_errcode_even_with_http_200(monkeypatch):
    """企微对失效 webhook 也回 HTTP 200，必须看 errcode（2026-09 通知实踩）。"""
    monkeypatch.setattr(notify.socket, "getaddrinfo", _fake_addrinfo("103.7.28.161"))
    monkeypatch.setattr(
        notify.urllib.request, "urlopen",
        lambda req, timeout=None: _Resp(json.dumps({"errcode": 40058, "errmsg": "exceed max length"}).encode()),
    )
    with pytest.raises(RuntimeError, match="errcode=40058"):
        notify.send_markdown("https://qyapi.example/cgi-bin/webhook/send?key=x", "t")


def test_send_rejects_non_json_response(monkeypatch):
    monkeypatch.setattr(notify.socket, "getaddrinfo", _fake_addrinfo("103.7.28.161"))
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b"<html>gate</html>"))
    with pytest.raises(RuntimeError, match="非 JSON"):
        notify.send_markdown("https://qyapi.example/cgi-bin/webhook/send?key=x", "t")


def test_send_success_passthrough(monkeypatch):
    monkeypatch.setattr(notify.socket, "getaddrinfo", _fake_addrinfo("103.7.28.161"))
    payload = json.dumps({"errcode": 0, "errmsg": "ok"}).encode()
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=None: _Resp(payload))
    out = notify.send_markdown("https://qyapi.example/cgi-bin/webhook/send?key=x", "t")
    assert out == {"errcode": 0, "errmsg": "ok"}
