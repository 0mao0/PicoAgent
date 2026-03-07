from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable


class SyncError(RuntimeError):
    """同步失败时抛出的错误。"""


def load_scripts(package_json_path: Path) -> dict[str, str]:
    """读取 package.json 中的 scripts 定义。"""
    data = json.loads(package_json_path.read_text(encoding="utf-8"))
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        raise SyncError("package.json scripts 字段格式无效")
    return {str(k): str(v) for k, v in scripts.items()}


def _pick_commands(scripts: dict[str, str], keys: list[str], include_install: bool = True) -> list[str]:
    """按顺序提取命令清单。"""
    commands: list[str] = []
    if include_install:
        commands.append("pnpm install")
    for key in keys:
        if key in scripts:
            commands.append(f"pnpm {key}")
    return commands


def render_apps_tech_commands(scripts: dict[str, str]) -> str:
    """渲染前端技术文档命令区块。"""
    commands = _pick_commands(
        scripts,
        ["dev:frontend", "dev:admin", "build:frontend", "build:admin", "lint", "docs:sync", "docs:check"],
    )
    body = "\n".join(commands)
    return f"```bash\n{body}\n```"


def render_services_tech_commands(scripts: dict[str, str]) -> str:
    """渲染后端技术文档命令区块。"""
    commands = _pick_commands(
        scripts,
        ["dev:backend", "harness", "harness:workflow", "harness:tooling", "docs:sync", "docs:check"],
    )
    body = "\n".join(commands)
    return f"```bash\n{body}\n```"


def replace_block(content: str, start_marker: str, end_marker: str, new_block: str) -> tuple[str, bool]:
    """替换标记区块并返回是否发生变化。"""
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start < 0 or end < 0 or end < start:
        raise SyncError(f"未找到有效标记: {start_marker} / {end_marker}")
    body_start = start + len(start_marker)
    updated = content[:body_start] + "\n" + new_block + "\n" + content[end:]
    return updated, updated != content


def sync_marked_file(
    path: Path,
    start_marker: str,
    end_marker: str,
    renderer: Callable[[dict[str, str]], str],
    scripts: dict[str, str],
    check: bool,
) -> bool:
    """同步单个文档的目标区块。"""
    original = path.read_text(encoding="utf-8")
    rendered = renderer(scripts)
    updated, changed = replace_block(original, start_marker, end_marker, rendered)
    if changed and not check:
        path.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    """执行文档同步或漂移检查。"""
    parser = argparse.ArgumentParser(description="同步技术说明文档中的自动维护区块")
    parser.add_argument("--check", action="store_true", help="仅检查是否存在漂移，不写入文件")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    scripts = load_scripts(repo_root / "package.json")

    targets = [
        (
            repo_root / "apps/Techniques.md",
            "<!-- AUTO_SYNC:APPS_TECH_COMMANDS:START -->",
            "<!-- AUTO_SYNC:APPS_TECH_COMMANDS:END -->",
            render_apps_tech_commands,
        ),
        (
            repo_root / "services/Techniques.md",
            "<!-- AUTO_SYNC:SERVICES_TECH_COMMANDS:START -->",
            "<!-- AUTO_SYNC:SERVICES_TECH_COMMANDS:END -->",
            render_services_tech_commands,
        ),
    ]

    changed_files: set[Path] = set()
    for path, start_marker, end_marker, renderer in targets:
        changed = sync_marked_file(path, start_marker, end_marker, renderer, scripts, args.check)
        if changed:
            changed_files.add(path)

    if args.check and changed_files:
        for path in sorted(changed_files):
            print(f"文档需要同步: {path}")
        return 1

    if not args.check:
        if changed_files:
            for path in sorted(changed_files):
                print(f"已同步: {path}")
        else:
            print("无需同步，文档已是最新状态")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
