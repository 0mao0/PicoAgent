"""nightly 结果 → 企微卡片（三态严格区分；算法真相源，scripts 侧 CLI 复用）。

nightly 首跑实踩：评测步骤中途炸了、门禁产物不存在，旧内联脚本却把"未获取到
gate.json"渲染成绿色"评测通过"——从此绿色必须有 gate 结论背书，缺一律 error。

卡片必须带真实结果与基线差异（Δpp+CI、过渡矩阵）——用户视角是"测试集重新跑一遍
的结果和与基线的区别"，不是一句"通过"。
"""
import ipaddress
import json
import re
import socket
import urllib.request
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from urllib.parse import urlparse

STATE_GREEN, STATE_RED, STATE_ERROR = "green", "red", "error"
_HEADS = {STATE_GREEN: "**🟢 AnGIneer nightly 评测通过**",
          STATE_RED: "**🔴 AnGIneer nightly 评测回归**",
          STATE_ERROR: "**⚠️ AnGIneer nightly 评测执行失败**"}


def _pct(value):
    return f"{value * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def fmt_span(started_at, completed_at) -> Tuple[str, str]:
    """run 起止（UTC → 北京时间）与时长。字段缺失一律 '—'，通知不许造时间。"""
    try:
        start = datetime.fromisoformat(str(started_at)) + timedelta(hours=8)
        end = datetime.fromisoformat(str(completed_at)) + timedelta(hours=8)
        minutes = max(0, int((end - start).total_seconds() // 60))
        span = f"{start:%m-%d %H:%M} – {end:%H:%M}"
        duration = f"{minutes // 60}h{minutes % 60:02d}m"
        return span, duration
    except (TypeError, ValueError):
        return "—", "—"


def build_message(raw: Optional[dict], gate: Optional[dict], state: str, error_note: str = "") -> str:
    """一行一项：时间 / 时长 / 结果 / 分析。详情进站点页，不进卡片。"""
    summary = (raw or {}).get("summary_scores") or {}
    span, duration = fmt_span((raw or {}).get("started_at"), (raw or {}).get("completed_at"))
    lines = [_HEADS.get(state, _HEADS[STATE_ERROR])]
    lines.append(f"时间：{span}")
    lines.append(f"时长：{duration}")
    if summary:
        lines.append(
            f"结果：**{_pct(summary.get('overall_score'))}**"
            f"（正确 {summary.get('correct', '?')}/{summary.get('total', '?')}）"
            f"｜judge 异常 {summary.get('judge_failed_count', '?')}"
            f"｜执行错误 {summary.get('errored', 0)}"
        )
    else:
        lines.append("结果：—（未产出评测结果）")
    if gate:
        m = gate.get("matrix") or {}
        delta = gate.get("delta")
        if isinstance(delta, (int, float)):
            pp = abs(delta) * 100
            move = "提升" if delta > 0.002 else ("下降" if delta < -0.002 else "基本持平")
            net = m.get("pf", 0) - m.get("fp", 0)
            tail = "，存在显著回归" if state == STATE_RED else ("，无显著回归" if delta > -0.002 else "，需关注")
            lines.append(f"分析：较基线{move} {pp:.1f} 个百分点（净{'增' if net >= 0 else '退'} {abs(net)} 题）{tail}。")
        else:
            lines.append("分析：门禁产物不完整，见服务器日志。")
    elif state == STATE_ERROR:
        lines.append(f"分析：评测环节未完成（{error_note or '见服务器日志'}），无结论。")
    else:
        lines.append("分析：门禁产物缺失，见服务器日志。")
    return "\n".join(lines)


def append_links(text: str, site_url: str = "", run_label: str = "") -> str:
    """查看链接：站点优先；有 run 记录可加一条溯源说明。"""
    if site_url:
        return text + f"\n查看：[夜间维护]({site_url})"
    return text


def split_webhooks(raw: str) -> List[str]:
    """WEBHOOK 配置支持逗号/分号/空白（含换行）分隔多个群机器人，去重保序。

    密钥只从环境变量读取，严禁写进源码/示例/测试。"""
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


def _validate_webhook_url(url: str) -> None:
    """SSRF 边界：仅允许 http/https，且解析后地址必须为公网（拒 localhost/环回/私有/保留段）。"""
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


def send(webhook: str, text: str) -> str:
    """单群推送：发送前校验 URL，发送后校验企微返回的 errcode——
    企微对失效 webhook 也回 HTTP 200，不校验 errcode 会把拒收当送达（2026-09 通知实踩）。"""
    _validate_webhook_url(webhook)
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": text}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
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
    return payload
