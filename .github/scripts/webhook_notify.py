"""Send WeCom webhook notification for deployment."""
import ipaddress
import json
import os
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from urllib.parse import urlparse


def _validate_webhook(url: str) -> str:
    """服务端请求边界：仅 https + 企微机器人开放域名白名单，解析后拒绝私网/环回/链路本地/保留地址。"""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SystemExit("WEBHOOK must use https")
    host = parsed.hostname or ""
    if host != "qyapi.weixin.qq.com":
        raise SystemExit(f"WEBHOOK host not allowed: {host!r} (only qyapi.weixin.qq.com)")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise SystemExit(f"WEBHOOK host does not resolve: {exc}")
    if not infos:
        raise SystemExit("WEBHOOK host resolved to no addresses")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise SystemExit(f"WEBHOOK host resolves to disallowed address: {ip}")
    return url


webhook = os.environ.get("WEBHOOK", "")
if not webhook:
    print("WEBHOOK not set, skipping")
    sys.exit(0)
webhook = _validate_webhook(webhook)


def _git(args):
    return subprocess.Popen(
        ["git"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo,
    ).communicate()[0].decode().strip()


# repo root is parent of .github/scripts/ directory
repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sha = _git(["log", "-1", "--format=%H"])[:7]
msg = _git(["log", "-1", "--format=%s"])
ref = _git(["rev-parse", "--abbrev-ref", "HEAD"])

fe = os.environ.get("FE", "?")
adm = os.environ.get("ADM", "?")
api = os.environ.get("API", "?")
run_url = os.environ.get("RUN_URL", "")
prev_sha = os.environ.get("PREV_SHA", "").strip()

# 汇总本次 push 的提交：部署工作流在上一次部署后记录的 HEAD（PREV_SHA）到当前 HEAD 的提交列表
commit_lines = []
prev_exists = False
if prev_sha:
    check = subprocess.run(
        ["git", "cat-file", "-e", prev_sha + "^{commit}"],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    prev_exists = check.returncode == 0
if prev_exists:
    log = _git(["log", "--oneline", "--no-merges", f"{prev_sha}..HEAD"])
    all_commits = [line for line in log.splitlines() if line.strip()]
    commit_lines = all_commits[:15]
    total = len(all_commits)
else:
    total = 1

def _release_version() -> str:
    """版本号以根 package.json 为准（发版约定与 README/tag 三处同步）；读取失败退回最近 tag。"""
    try:
        with open(os.path.join(repo, "package.json"), encoding="utf-8") as fh:
            version = str(json.load(fh).get("version") or "")
        if version:
            return version if version.startswith("v") else "v" + version
    except Exception:  # noqa: BLE001
        pass
    return _git(["describe", "--tags", "--abbrev=0"]) or "unknown"


content_parts = ["## ✅ AnGIneer 部署完成", f"> **版本:** `{_release_version()}`"]
if prev_exists:
    content_parts.append(f"> **本次提交:** `{total}` 个")
    for line in commit_lines:
        content_parts.append(f"> {line}")
    if total > len(commit_lines):
        content_parts.append(f"> … 共 {total} 个提交")
else:
    content_parts.append(f"> **提交:** `{sha}` - {msg}")
content_parts += [
    f"> **分支:** `{ref}`",
    f"> **时间:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
    "",
    "**服务状态**",
    f"> 前台: `{fe}`",
    f"> 管理后台: `{adm}`",
    f"> API 文档: `{api}`",
]
if run_url:
    content_parts.append("")
    content_parts.append(f"[查看 Actions]({run_url})")
content = "\n".join(content_parts)

payload = json.dumps(
    {"msgtype": "markdown", "markdown": {"content": content}},
    ensure_ascii=False,
).encode("utf-8")
class _ForbidRedirect(urllib.request.HTTPRedirectHandler):
    """目标地址只允许经过白名单校验的固定端点：跟随重定向会绕过边界校验（rebinding 面）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, "redirects are forbidden for webhook", headers, fp)


req = urllib.request.Request(
    webhook,  # 已经过 _validate_webhook：https + qyapi.weixin.qq.com 白名单 + 解析 IP 边界
    data=payload,
    headers={"Content-Type": "application/json; charset=utf-8"},
)
opener = urllib.request.build_opener(_ForbidRedirect())
resp = opener.open(req)
print("WeCom notify status:", resp.status)
# 企微机器人对失效 webhook 也返回 HTTP 200，真实投递结果在响应体 errcode——
# 必须解析并以显性失败收口（此前只打印 HTTP 状态码，通知丢了 job 依旧绿）
try:
    body = json.loads(resp.read().decode("utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"::error::WeCom notify response body unparsable: {exc}")
    sys.exit(1)
if int(body.get("errcode", 0)) != 0:
    print(f"::error::WeCom notify rejected: errcode={body.get('errcode')} errmsg={body.get('errmsg')}")
    sys.exit(1)
print("WeCom notify delivered (errcode=0)")
