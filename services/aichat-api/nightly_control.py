"""夜间维护调度控制：Web 端配置 + 内置调度器直接跑流水线（全内置，不经过 GitHub）。

时间口径为北京时间；配置持久化在 data/evals/nightly_settings.json（改配置 1 分钟内
生效，零部署）。到点执行的是 evals_core.nightly.pipeline.run_nightly —— 与「开始
评测」按钮同一套 suite_runner。服务器 .env 配 NIGHTLY_SCHEDULER=1 启用定时器；
「立即运行」在任何环境都可用（本地跑小集合验证用）。
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from evals_core.nightly import paths, pipeline

logger = logging.getLogger("nightly_control")

BJT = paths.BJT
DEFAULT_SETTINGS = {
    "enabled": False,
    "hour": 1,
    "minute": 0,
    "dataset_id": paths.DATASET_DEFAULT,
    "timeout_minutes": 270,       # 487 题全量含补判最坏 4.5h
    "retry_rounds": 2,
}
HOURLY_WINDOW = (0, 23)
MINUTE_WINDOW = (0, 59)
TIMEOUT_WINDOW = (10, 1440)
RETRY_WINDOW = (0, 3)


def normalize_settings(raw: dict) -> dict:
    """校验+归一（PUT 入参）；非法抛 ValueError（路由层转 400）。"""
    if not isinstance(raw, dict):
        raise ValueError("请求体必须是对象")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("enabled 必须是布尔")

    def _int(key: str, default: int, low: int, high: int) -> int:
        try:
            val = int(raw.get(key, default))
        except (TypeError, ValueError):
            raise ValueError(f"{key} 必须是整数")
        if not low <= val <= high:
            raise ValueError(f"{key} 需在 {low}-{high}")
        return val

    if "dataset_id" in raw:
        dataset_id = str(raw.get("dataset_id") or "").strip()
        if not dataset_id or any(c in dataset_id for c in "/\\.."):
            raise ValueError("dataset_id 不合法")
    else:
        dataset_id = DEFAULT_SETTINGS["dataset_id"]
    return {
        "enabled": enabled,
        "hour": _int("hour", DEFAULT_SETTINGS["hour"], *HOURLY_WINDOW),
        "minute": _int("minute", DEFAULT_SETTINGS["minute"], *MINUTE_WINDOW),
        "dataset_id": dataset_id,
        "timeout_minutes": _int("timeout_minutes", DEFAULT_SETTINGS["timeout_minutes"], *TIMEOUT_WINDOW),
        "retry_rounds": _int("retry_rounds", DEFAULT_SETTINGS["retry_rounds"], *RETRY_WINDOW),
    }


def load_settings() -> dict:
    cfg = dict(DEFAULT_SETTINGS)
    last_dispatch = None
    try:
        data = json.loads(paths.settings_file().read_text(encoding="utf-8"))
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
    path = paths.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: cfg[k] for k in DEFAULT_SETTINGS}
    if cfg.get("last_dispatch"):
        payload["last_dispatch"] = cfg["last_dispatch"]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def next_fire_at(cfg: dict, now: datetime) -> Optional[datetime]:
    """下一次应触发的绝对时刻（Asia/Shanghai）。未启用返回 None。"""
    if not cfg.get("enabled"):
        return None
    local = now.astimezone(BJT)
    candidate = local.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def slot_of(cfg: dict, now: datetime) -> str:
    """"当天该时段"幂等键：北京日期 + 配置时刻。"""
    return f"{now.astimezone(BJT).date().isoformat()} {cfg['hour']:02d}:{cfg['minute']:02d}"


def due(cfg: dict, now: datetime) -> bool:
    """启用、已到今日时段、且该时段未触发过 → 该跑。"""
    if not cfg.get("enabled"):
        return False
    local = now.astimezone(BJT)
    if local.hour * 60 + local.minute < cfg["hour"] * 60 + cfg["minute"]:
        return False
    last = cfg.get("last_dispatch") or {}
    return last.get("slot") != slot_of(cfg, now)


# ── 流水线触发（进程内唯一，天然替代 GH 的 concurrency 锁）──

_active: Optional[asyncio.Task] = None


def is_running() -> bool:
    return _active is not None and not _active.done()


def _record(cfg: dict, now: datetime, source: str, slot: Optional[str], result: dict) -> None:
    cfg = dict(cfg)
    cfg["last_dispatch"] = {
        "slot": slot if source == "scheduler" else f"manual:{now.astimezone(BJT).isoformat(timespec='minutes')}",
        "source": source,
        "at": now.astimezone(BJT).isoformat(timespec="seconds"),
        "ok": bool(result.get("ok")),
        "state": result.get("state") or ("error" if not result.get("ok") else "green"),
        "run_id": result.get("run_id") or "",
        "detail": str(result.get("detail") or "")[:300],
    }
    try:
        save_settings(cfg)
    except OSError:
        logger.exception("nightly 运行结果落盘失败")


async def _execute(cfg: dict, source: str, slot: Optional[str]) -> dict:
    t0 = time.monotonic()
    webhook = (os.getenv("NIGHTLY_WECOM_WEBHOOK") or os.getenv("WEBHOOK") or "").strip()
    site_url = (os.getenv("NIGHTLY_SITE_URL") or "https://angineer.cn/admin/evals?view=nightly").strip()
    logger.info("nightly 流水线开始（source=%s, dataset=%s）", source, cfg["dataset_id"])
    result = await pipeline.run_nightly(
        dataset_id=cfg["dataset_id"],
        timeout_hours=cfg["timeout_minutes"] / 60.0,
        retry_rounds=cfg["retry_rounds"],
        site_url=site_url,
        webhook=webhook,
    )
    logger.info("nightly 流水线结束（source=%s）: state=%s 用时 %.1f min",
                source, result.get("state"), (time.monotonic() - t0) / 60.0)
    _record(cfg, datetime.now(BJT), source, slot, result)
    return result


async def launch(source: str = "manual", slot: Optional[str] = None) -> dict:
    """后台启动流水线；已在跑则拒绝（返回 ok=False）。返回启动状态（非评测结果）。"""
    global _active
    if is_running():
        return {"ok": False, "detail": "已有一条夜间流水线在运行，请等待其完成"}
    cfg = load_settings()
    _active = asyncio.create_task(_execute(cfg, source, slot))
    return {"ok": True, "started_at": datetime.now(BJT).isoformat(timespec="seconds"),
            "detail": "流水线已在后台启动，预计数十分钟至数小时，完成看企微与本页历史"}


async def scheduler_loop() -> None:
    """轻量轮询：睡到下一个检查点（≤1h，配置变更 1 分钟内生效），到点直接跑流水线。"""
    logger.info("nightly 调度器已启动（时区 Asia/Shanghai，全内置流水线）")
    while True:
        try:
            now = datetime.now(BJT)
            cfg = load_settings()
            wait = 60.0
            nxt = next_fire_at(cfg, now)
            if nxt is not None:
                wait = min(max((nxt - now).total_seconds(), 5.0), 3600.0)
            await asyncio.sleep(wait)
            now = datetime.now(BJT)
            cfg = load_settings()
            if not due(cfg, now) or is_running():
                continue
            await _execute(cfg, "scheduler", slot_of(cfg, now))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 调度循环永不因单次失败退出
            logger.exception("nightly 调度迭代异常，60s 后继续")
            await asyncio.sleep(60)
