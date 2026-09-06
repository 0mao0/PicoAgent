"""夜间维护调度控制：Web 端配置持久化 + 到点触发 eval-nightly workflow。

触发权从 GitHub cron 迁到服务器（cron 不守时——2026-09-06 实到延迟近 2h——且改时间
要改 yml 走 commit）；本模块只决定"何时触发"，评测执行仍走 eval-nightly.yml 的
workflow_dispatch 全链路（eval→gate→publish→企微），不复制任何评测逻辑。

服务器启用需 .env 配：NIGHTLY_SCHEDULER=1、NIGHTLY_GH_TOKEN（细粒度 PAT，
仅 AnGIneer 仓库 Actions 读写）、可选 NIGHTLY_GH_REPO / NIGHTLY_GH_REF。
"""
import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("nightly_control")

BJT = ZoneInfo("Asia/Shanghai")
WORKFLOW_FILE = "eval-nightly.yml"
DEFAULT_SETTINGS = {"enabled": False, "hour": 1, "minute": 0}
HOUR_RANGE = (0, 23)
MINUTE_RANGE = (0, 59)


def settings_file() -> Path:
    """配置与 evals.sqlite 同目录（data/evals/nightly_settings.json）；env 可覆盖（测试用）。"""
    env = os.getenv("NIGHTLY_SETTINGS_FILE", "").strip()
    if env:
        return Path(env)
    from evals_core.storage import result_store
    return Path(result_store._DB_PATH).parent / "nightly_settings.json"


def normalize_settings(raw: dict) -> dict:
    """校验+归一（PUT 入参）；非法抛 ValueError（路由层转 400）。只认白名单键。"""
    if not isinstance(raw, dict):
        raise ValueError("请求体必须是对象")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("enabled 必须是布尔")
    try:
        hour = int(raw.get("hour", DEFAULT_SETTINGS["hour"]))
        minute = int(raw.get("minute", DEFAULT_SETTINGS["minute"]))
    except (TypeError, ValueError):
        raise ValueError("hour/minute 必须是整数")
    if not HOUR_RANGE[0] <= hour <= HOUR_RANGE[1]:
        raise ValueError(f"hour 需在 {HOUR_RANGE[0]}-{HOUR_RANGE[1]}")
    if not MINUTE_RANGE[0] <= minute <= MINUTE_RANGE[1]:
        raise ValueError(f"minute 需在 {MINUTE_RANGE[0]}-{MINUTE_RANGE[1]}")
    return {"enabled": enabled, "hour": hour, "minute": minute}


def load_settings() -> dict:
    cfg = dict(DEFAULT_SETTINGS)
    last_dispatch = None
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update(normalize_settings(data))
            ld = data.get("last_dispatch")
            if isinstance(ld, dict):
                last_dispatch = ld
    except (OSError, ValueError):
        pass  # 文件缺失/损坏 → 默认值（enabled=False），接口仍可用
    cfg["last_dispatch"] = last_dispatch
    return cfg


def save_settings(cfg: dict) -> None:
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"enabled": bool(cfg.get("enabled")), "hour": int(cfg["hour"]), "minute": int(cfg["minute"])}
    if cfg.get("last_dispatch"):
        payload["last_dispatch"] = cfg["last_dispatch"]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def next_fire_at(cfg: dict, now: datetime) -> datetime | None:
    """下一次应触发的绝对时刻（Asia/Shanghai）。未启用返回 None。"""
    if not cfg.get("enabled"):
        return None
    local = now.astimezone(BJT)
    candidate = local.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def slot_of(cfg: dict, now: datetime) -> str:
    """"当天该时段"幂等键：北京日期 + 配置时刻（last_dispatch.slot 与之相同则已触发过）。"""
    return f"{now.astimezone(BJT).date().isoformat()} {cfg['hour']:02d}:{cfg['minute']:02d}"


def due(cfg: dict, now: datetime) -> bool:
    """启用、已过/到达今日时段、且该时段未触发过 → 该 dispatch。"""
    if not cfg.get("enabled"):
        return False
    local = now.astimezone(BJT)
    if local.hour * 60 + local.minute < cfg["hour"] * 60 + cfg["minute"]:
        return False
    last = cfg.get("last_dispatch") or {}
    return last.get("slot") != slot_of(cfg, now)


def dispatch_github(source: str) -> dict:
    """POST workflow_dispatch（同步函数，调度器经 to_thread 调）。永不抛。"""
    token = os.getenv("NIGHTLY_GH_TOKEN", "").strip()
    repo = os.getenv("NIGHTLY_GH_REPO", "0mao0/AnGIneer").strip()
    ref = os.getenv("NIGHTLY_GH_REF", "main").strip()
    if not token:
        return {"ok": False, "detail": "服务器未配置 NIGHTLY_GH_TOKEN"}
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    body = json.dumps({"ref": ref, "client_payload": {"source": source}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "angineer-nightly-control",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 固定 https 端点
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "detail": ""}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(300).decode("utf-8", "replace")
        except OSError:
            detail = ""
        logger.warning("workflow_dispatch 失败 HTTP %s: %s", exc.code, detail)
        return {"ok": False, "status": exc.code, "detail": detail}
    except Exception as exc:  # noqa: BLE001 网络异常只记录，不影响服务
        logger.warning("workflow_dispatch 异常: %s", exc)
        return {"ok": False, "detail": str(exc)[:300]}


def record_dispatch(cfg: dict, now: datetime, source: str, result: dict) -> dict:
    """把触发结果写回配置（slot 幂等 + 站点展示"上次触发"）。"""
    cfg = dict(cfg)
    cfg["last_dispatch"] = {
        "slot": slot_of(cfg, now) if source == "scheduler" else f"manual:{now.astimezone(BJT).isoformat(timespec='minutes')}",
        "source": source,
        "at": now.astimezone(BJT).isoformat(timespec="seconds"),
        "ok": bool(result.get("ok")),
        "detail": str(result.get("detail") or "")[:300],
    }
    save_settings(cfg)
    return cfg


async def scheduler_loop() -> None:
    """轻量轮询调度：睡到下一个检查点（≤1h，配置变更 1 分钟内生效），到点即触发。"""
    logger.info("nightly 调度器已启动（时区 Asia/Shanghai）")
    while True:
        try:
            now = datetime.now(timezone.utc)
            cfg = load_settings()
            wait = 60.0
            nxt = next_fire_at(cfg, now)
            if nxt is not None:
                wait = min(max((nxt - now).total_seconds(), 5.0), 3600.0)
            await asyncio.sleep(wait)
            now = datetime.now(timezone.utc)
            cfg = load_settings()
            if not due(cfg, now):
                continue
            logger.info("nightly 调度触发：slot=%s", slot_of(cfg, now))
            result = await asyncio.to_thread(dispatch_github, "scheduler")
            record_dispatch(cfg, now, "scheduler", result)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 调度循环永不因单次失败退出
            logger.exception("nightly 调度迭代异常，60s 后继续")
            await asyncio.sleep(60)
