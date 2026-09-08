"""统一 webhook 通知模块。

所有企微机器人推送都走这里，URL 校验 + 多群推送 + errcode 校验一次实现。
"""
import ipaddress
import json
import re
import socket
import urllib.request
from typing import List
from urllib.parse import urlparse


def split_webhooks(raw: str) -> List[str]:
    """逗号/分号/空白分隔多 URL，去重保序。"""
    seen, out = set(), []
    for part in re.split(r"[,;\s]+", (raw or "").strip()):
        if part and part not in seen:
            seen.add(part)
            out.append(part)
    return out


def target_label(url: str) -> str:
    """日志用目标标识：只留 scheme://host，绝不回显含 key 的完整 URL。"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else "<无效地址>"
    except ValueError:
        return "<无效地址>"


def validate_webhook_url(url: str) -> None:
    """SSRF 防护：仅允许 http/https，且解析后地址必须为公网。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"webhook 协议不合法（仅 http/https）: {target_label(url)}")
    if parsed.username or parsed.password:
        raise ValueError(f"webhook 不允许内嵌凭据: {target_label(url)}")
    if not parsed.hostname:
        raise ValueError("webhook 缺少主机名")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port)
    except socket.gaierror as exc:
        raise ValueError(f"webhook 域名解析失败: {target_label(url)}") from exc
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            raise ValueError(f"webhook 解析出非法地址: {target_label(url)}") from None
        if (ip.is_private or ip.is_loopback or ip.is_reserved
                or ip.is_link_local or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"webhook 指向非公网地址，已拒绝: {target_label(url)}")


def send_markdown(webhook: str, content: str) -> dict:
    """单群发送 Markdown 消息，校验 errcode。

    企微对失效 webhook 也回 HTTP 200，必须检查 errcode。
    """
    validate_webhook_url(webhook)
    body = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = resp.read().decode()
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise RuntimeError(f"企微 webhook 返回非 JSON: {payload[:200]!r}") from exc
    if data.get("errcode") != 0:
        raise RuntimeError(
            f"企微 webhook 拒收: errcode={data.get('errcode')} errmsg={data.get('errmsg', '')}"
        )
    return data


def send(
    webhook: str,
    content: str,
    *,
    quiet: bool = False,
) -> List[dict]:
    """多群推送：单群失败不阻断，全失败才抛异常。

    Args:
        webhook: 支持逗号/分号/空白分隔的多个 URL
        content: Markdown 格式消息内容
        quiet: 单群失败时是否打印到 stderr
    """
    targets = split_webhooks(webhook)
    if not targets:
        if not quiet:
            print("[notify] 未配置 WEBHOOK，跳过通知")
        return []

    bodies, errors = [], []
    for url in targets:
        try:
            bodies.append(send_markdown(url, content))
        except Exception as exc:
            errors.append(f"{target_label(url)}: {exc}")
            if not quiet:
                print(f"[notify] 推送失败 {target_label(url)}: {exc}")

    if errors and not bodies:
        raise RuntimeError("; ".join(errors))
    return bodies
