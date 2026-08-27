"""Send WeCom webhook notification for @angineer/* package release."""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime


def changelog_desc(tag, max_lines=3, max_chars=60):
    """从 CHANGELOG.md 中匹配版本的条目提取发版简介（最多前 3 条 bullet）。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "CHANGELOG.md")
    if not os.path.isfile(path):
        return ""
    ver = tag.lstrip("vV")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    bullets = []
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("###"):
            continue
        if line.startswith("#"):
            in_section = False
            head = line.lstrip("#").strip()
            first = head.split()[0] if head.split() else ""
            first = first.split("：")[0].split("(")[0]
            if first.lstrip("vV") == ver:
                in_section = True
            continue
        if in_section and line.startswith(("-", "*")):
            item = line.lstrip("-*").strip()
            if len(item) > max_chars:
                item = item[: max_chars - 1] + "…"
            bullets.append(item)
            if len(bullets) >= max_lines:
                break
    return "；".join(bullets)


def _git(args):
    return subprocess.Popen(
        ["git"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo,
    ).communicate()[0].decode(errors="replace").strip()


# repo root is parent of .github/scripts/ directory
repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

webhook = os.environ.get("WEBHOOK", "")
if not webhook:
    print("WEBHOOK not set, skipping")
    sys.exit(0)

package = os.environ.get("PACKAGE", "angineer")
tag = os.environ.get("TAG", "")
sha = os.environ.get("SHA", "")[:7]
run_url = os.environ.get("RUN_URL", "")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
intro = os.environ.get("INTRO", "").strip()[:8]
desc = os.environ.get("DESC", "").strip()
if not desc and tag:
    desc = changelog_desc(tag)

# 汇总自上一个版本 tag 以来的提交明细，方便群里直接看到本次发布了什么
commit_lines = []
total = 0
prev_tag = ""
if tag:
    prev_tag = _git(["describe", "--tags", "--abbrev=0", f"{tag}^"])
    if prev_tag:
        log = _git(["log", "--oneline", "--no-merges", f"{prev_tag}..{tag}"])
        all_commits = [line for line in log.splitlines() if line.strip()]
        total = len(all_commits)
        commit_lines = all_commits[:15]

lines = [f"## 🚀 {package} 发布"]
if intro:
    lines.append(f"> **介绍:** {intro}")
if tag:
    lines.append(f"> **版本:** `{tag}`")
if desc:
    lines.append(f"> **本次发版:** {desc}")
if total:
    lines.append(f"> **本次提交:** `{total}` 个")
    for line in commit_lines:
        lines.append(f"> {line}")
    if total > len(commit_lines):
        lines.append(f"> … 共 {total} 个提交")
elif sha:
    lines.append(f"> **提交:** `{sha}`")
lines.append(f"> **时间:** `{now}`")
if run_url:
    lines.append(f"\n[查看 Actions]({run_url})")
content = "\n".join(lines)

payload = json.dumps(
    {"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False
).encode("utf-8")
req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print("WeCom notify status:", resp.status)
