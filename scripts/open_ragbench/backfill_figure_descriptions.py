"""存量文档图描述回填：逐篇从 figure_describe 阶段重试（连带 fts/vectors/graph 重跑）。

stage retry 语义（docs_routes.py）：从指定阶段起连同后续阶段一起重跑，前置产物复用。
因此每篇只需一次 retry figure_describe，即可完成「生成描述 → 重建索引」。

鉴权：全程走管理员 Bearer token（ADMIN_USER/ADMIN_PASSWORD，.env），
触发 retry 与轮询任务（/api/knowledge/parse/tasks/{task_id}）用同一个 token，无 keys.json 依赖。

队列来源三选一：
- --from-db：自动筛「completed 文档 ∧ 无 figure_describe completed 记录 ∧ 磁盘有 mineru_raw 产物」，
  即 backlog《存量文档图描述补齐》阶段 1 的 A 类清单（doc_blocks_graph.jsonl 里无图表块的记 skipped）；
- --doc-ids：显式指定；
- 默认：open_ragbench import_state 全部 succeeded（历史行为）。

进度持久化到 backfill_figure_state.json（断点续跑）。
"""
from __future__ import annotations  # 生产宿主机 python 较老，泛型注解需惰性化

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from open_ragbench import common  # noqa: E402

STATE_FILE = common.SUBSET_DIR / "backfill_figure_state.json"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(common.REPO_ROOT / ".env")


def login_admin(ep: common.Endpoints, username: str, password: str) -> str:
    resp = requests.post(ep.login, json={"username": username, "password": password}, timeout=30)
    resp.raise_for_status()
    return resp.json()["token"]


def _with_conn_retries(make, attempts: int = 20, wait: int = 30):
    """docs-api 重启/重建窗口内连接会被拒（deploy 实踩：容器重建 2 分钟把整队 77 篇烧光）。
    连接类异常重试等待恢复；HTTP 4xx/5xx 不在此列，交由调用方判定。"""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return make()
        except requests.ConnectionError as exc:
            last = exc
            print(f"  连接失败（服务可能在重启），{wait}s 后重试: {type(exc).__name__}", flush=True)
            time.sleep(wait)
    raise last  # type: ignore[misc]


def trigger_retry(ep: common.Endpoints, token: str, doc_id: str, stage_key: str) -> str:
    resp = _with_conn_retries(lambda: requests.post(
        f"{ep.docs_api}/api/knowledge/documents/{doc_id}/stages/{stage_key}/retry",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    ))
    if resp.status_code == 400 and "正在解析中" in resp.text:
        raise RuntimeError(f"文档正在解析中，跳过: {doc_id}")
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("id") or data.get("task_id") or ""
    if not task_id:
        raise RuntimeError(f"retry 响应缺少任务 ID: {data}")
    return task_id


def poll_task_status(ep: common.Endpoints, token: str, task_id: str, timeout: int, interval: int) -> str:
    """轮询 /api/knowledge/parse/tasks/{task_id}（管理员 Bearer），partial 视同成功（soft 阶段兜底）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{ep.docs_api}/api/knowledge/parse/tasks/{task_id}",
                headers={"Authorization": f"Bearer {token}"}, timeout=30,
            )
            resp.raise_for_status()
        except requests.ConnectionError:
            time.sleep(interval)  # 服务重启窗口：继续等，下一轮再试
            continue
        status = (resp.json().get("status") or "").lower()
        if status == "completed":
            return "succeeded"
        if status == "partial":
            return "partial"
        if status in ("failed", "cancelled"):
            return "failed"
        time.sleep(interval)
    return "timeout"


# 与 docs_core.step04_structure.figure_describer.FIGURE_TYPES 保持同集合（不 import 以免拉整个 docs-core）
_FIGURE_TYPES = {"chart", "image", "figure", "image_block"}


def _kb_base_dir(override: str = "") -> Path:
    return Path(override or os.getenv("KNOWLEDGE_BASE_DIR") or common.REPO_ROOT / "data" / "knowledge_base")


def _doc_parsed_dir(base_dir: Path, library_id: str, doc_id: str) -> Path:
    return base_dir / "libraries" / library_id / "documents" / doc_id / "parsed"


def collect_from_db(base_dir: Path) -> tuple[list[str], dict[str, str]]:
    """从 knowledge_meta.sqlite + 磁盘实况筛 A 类回填队列。

    返回 (doc_ids, skipped)；skipped 记录 doc_id -> 跳过原因：
    - no-mineru_raw：磁盘无解析产物（B 类，重传源文件后再处理）
    - no-graph-jsonl / no-figure-blocks：产物在手但没有任何图表块，跑 retry 只会白白重建索引
    """
    meta_db = base_dir / "knowledge_meta.sqlite"
    if not meta_db.exists():
        raise SystemExit(f"知识库元数据库不存在: {meta_db}（KNOWLEDGE_BASE_DIR/--base-dir 是否指对？）")
    queue: list[str] = []
    skipped: dict[str, str] = {}
    conn = sqlite3.connect(f"file:{meta_db.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT n.id, n.library_id FROM nodes n
            WHERE n.type='document' AND n.status='completed'
              AND NOT EXISTS (
                  SELECT 1 FROM doc_parse_stages s
                  WHERE s.doc_id = n.id AND s.stage='figure_describe' AND s.status='completed')
            ORDER BY n.id
            """
        ).fetchall()
    finally:
        conn.close()
    for doc_id, library_id in rows:
        parsed = _doc_parsed_dir(base_dir, library_id, doc_id)
        if not (parsed / "mineru_raw").is_dir():
            skipped[doc_id] = "no-mineru_raw"
            continue
        graph = parsed / "doc_blocks_graph.jsonl"
        if not graph.exists():
            skipped[doc_id] = "no-graph-jsonl"
            continue
        has_figure = False
        with open(graph, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    block = json.loads(line)
                except json.JSONDecodeError:
                    has_figure = True  # 解析不动就当有图，宁多跑不漏跑
                    break
                if str(block.get("block_type") or "") in _FIGURE_TYPES:
                    has_figure = True
                    break
        if not has_figure:
            skipped[doc_id] = "no-figure-blocks"
            continue
        queue.append(doc_id)
    return queue, skipped


def load_state() -> dict:
    if STATE_FILE.exists():
        return common.load_json(STATE_FILE)
    return {"done": {}, "failed": {}}


def save_state(state: dict) -> None:
    common.save_json(STATE_FILE, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="存量文档图描述回填")
    parser.add_argument("--docs-api", default="http://localhost:8790")
    parser.add_argument("--token", default="",
                        help="直接携带管理员 Bearer token（跳过 login；生产管理员密码不以 .env 为准时使用）")
    parser.add_argument("--doc-ids", default="", help="逗号分隔子集（优先于 --from-db）")
    parser.add_argument("--from-db", action="store_true",
                        help="按 knowledge_meta.sqlite+磁盘实况自动筛「缺图描述且有解析产物」的队列")
    parser.add_argument("--base-dir", default="", help="知识库根目录（默认 KNOWLEDGE_BASE_DIR 或 data/knowledge_base）")
    parser.add_argument("--dry-run", action="store_true", help="只打印队列与跳过清单，不触发任何任务")
    parser.add_argument("--poll-timeout", type=int, default=7200)
    parser.add_argument("--poll-interval", type=int, default=10)
    args = parser.parse_args()
    _load_env()

    if args.doc_ids:
        doc_ids = [d.strip() for d in args.doc_ids.split(",") if d.strip()]
        skipped: dict[str, str] = {}
    elif args.from_db:
        doc_ids, skipped = collect_from_db(_kb_base_dir(args.base_dir))
    else:
        state = common.load_json(common.IMPORT_STATE)
        papers = state.get("papers") or {}
        doc_ids = sorted({
            info.get("doc_id") for info in papers.values()
            if isinstance(info, dict) and info.get("status") in ("succeeded", "partial") and info.get("doc_id")
        })

    print(f"队列 {len(doc_ids)} 篇" + (f"，skipped {len(skipped)} 篇" if skipped else ""))
    for doc_id in doc_ids:
        print(f"  - {doc_id}")
    if skipped:
        reasons: dict[str, list[str]] = {}
        for doc_id, reason in skipped.items():
            reasons.setdefault(reason, []).append(doc_id)
        for reason, ids in sorted(reasons.items()):
            print(f"  skipped[{reason}] x{len(ids)}: {', '.join(sorted(ids))}")
    if args.dry_run:
        return 0
    if not doc_ids:
        return 0

    ep = common.Endpoints(docs_api=args.docs_api)
    if args.token:
        token = args.token
    else:
        admin_user = os.getenv("ADMIN_USER", "")
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if not admin_user or not admin_password:
            print("缺少 ADMIN_USER/ADMIN_PASSWORD（或改用 --token 直接携带管理员 token）")
            return 2
        token = login_admin(ep, admin_user, admin_password)
    progress = load_state()
    for doc_id in doc_ids:
        if doc_id in progress["done"] or doc_id in progress["failed"]:
            print(f"[{doc_id}] 已处理，跳过", flush=True)
            continue
        try:
            task_id = trigger_retry(ep, token, doc_id, "figure_describe")
            print(f"[{doc_id}] retry 任务 {task_id} 已提交", flush=True)
            status = poll_task_status(ep, token, task_id, args.poll_timeout, args.poll_interval)
            if status in ("succeeded", "partial"):
                progress["done"][doc_id] = {"task_id": task_id, "status": status}
                print(f"[{doc_id}] {status}", flush=True)
            else:
                progress["failed"][doc_id] = {"task_id": task_id, "status": status}
                print(f"[{doc_id}] 失败: {status}", flush=True)
        except Exception as exc:  # noqa: BLE001
            progress["failed"][doc_id] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"[{doc_id}] 异常: {exc}", flush=True)
        save_state(progress)

    print(f"回填完成: done={len(progress['done'])} failed={len(progress['failed'])}")
    return 0 if not progress["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
