"""nightly_control（内置调度器+流水线挂接）与 paths 约定单测：全内置，无 GitHub。"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for _rel in ("services/aichat-api", "services/evals-core/src"):
    p = os.path.join(ROOT, _rel)
    if p not in sys.path:
        sys.path.insert(0, p)

import nightly_control as nc  # noqa: E402
from evals_core.nightly import paths as npaths  # noqa: E402

BJT = ZoneInfo("Asia/Shanghai")


class _TmpSettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "nightly_settings.json")
        patch = mock.patch.dict(os.environ, {"NIGHTLY_SETTINGS_FILE": self.path})
        patch.start()
        self.addCleanup(patch.stop)


class PathsTests(unittest.TestCase):
    def test_default_paths_follow_result_store(self):
        from evals_core.storage import result_store
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(result_store, "_DB_PATH", str(Path(td) / "evals" / "evals.sqlite")):
                self.assertEqual(str(npaths.settings_file()),
                                 str(Path(td) / "evals" / "nightly_settings.json"))
                self.assertEqual(str(npaths.nightly_root()), str(Path(td) / "evals" / "nightly"))
                self.assertEqual(str(npaths.baseline_dir()), str(Path(td) / "evals" / "baseline"))
                self.assertEqual(str(npaths.dataset_json_path("ds-1")),
                                 str(Path(td) / "evals" / "datasets" / "ds-1.json"))
                self.assertEqual(str(npaths.manifest_path()),
                                 str(Path(td) / "open_ragbench" / "subset" / "subset_manifest_v2.json"))


class SettingsTests(_TmpSettings):
    def test_defaults_when_missing(self):
        cfg = nc.load_settings()
        self.assertEqual(cfg["enabled"], False)
        self.assertEqual((cfg["hour"], cfg["minute"]), (1, 0))
        self.assertEqual(cfg["dataset_id"], "open-ragbench-subset-v2")
        self.assertIsNone(cfg["last_dispatch"])

    def test_roundtrip_keeps_new_keys_and_history(self):
        cfg = nc.normalize_settings({"enabled": True, "hour": 2, "minute": 30,
                                     "dataset_id": "smoke", "timeout_minutes": 60, "retry_rounds": 1})
        cfg["last_dispatch"] = {"slot": "s", "ok": True}
        nc.save_settings(cfg)
        again = nc.load_settings()
        self.assertEqual(again["dataset_id"], "smoke")
        self.assertEqual((again["hour"], again["minute"]), (2, 30))
        self.assertEqual(again["timeout_minutes"], 60)
        self.assertEqual(again["last_dispatch"]["slot"], "s")

    def test_normalize_validation(self):
        ok = nc.normalize_settings({"enabled": True, "hour": 23, "minute": 59})
        self.assertEqual(ok["retry_rounds"], 2)  # 缺省补齐
        for bad in ({"hour": 24}, {"minute": 60}, {"timeout_minutes": 9}, {"retry_rounds": 4},
                    {"dataset_id": "a/../b"}, {"dataset_id": ""}, "not-dict", {"enabled": "yes"}):
            with self.assertRaises(ValueError):
                nc.normalize_settings(bad)

    def test_load_tolerates_corrupt_file(self):
        Path(self.path).write_text("{坏 json", encoding="utf-8")
        self.assertEqual(nc.load_settings()["enabled"], False)


class FireTimeTests(unittest.TestCase):
    def test_next_fire_uses_beijing_time(self):
        now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)  # 北京 17:00
        nxt = nc.next_fire_at({"enabled": True, "hour": 1, "minute": 0}, now)
        self.assertEqual(nxt.astimezone(BJT).strftime("%Y-%m-%d %H:%M"), "2026-09-07 01:00")

    def test_due_gate_slot_idempotent(self):
        cfg = {"enabled": True, "hour": 1, "minute": 0}
        before = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)
        after = datetime(2026, 9, 6, 17, 5, tzinfo=timezone.utc)
        self.assertFalse(nc.due(cfg, before))
        self.assertTrue(nc.due(cfg, after))
        self.assertFalse(nc.due(dict(cfg, last_dispatch={"slot": nc.slot_of(cfg, after)}), after))
        self.assertFalse(nc.due(dict(cfg, enabled=False), after))


class LaunchTests(unittest.TestCase):
    """launch 并发锁 + 结束后 last_dispatch 记录（scheduler 槽位幂等 / manual 不占槽）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"NIGHTLY_SETTINGS_FILE": str(Path(self.tmp.name) / "s.json")})
        env.start()
        self.addCleanup(env.stop)
        self.result = {"state": "green", "ok": True, "run_id": "run-x", "detail": ""}
        nc._active = None

    async def _fake_pipeline(self, **kwargs):
        return dict(self.result)

    def test_launch_records_manual_result(self):
        with mock.patch.object(nc.pipeline, "run_nightly", side_effect=self._fake_pipeline):
            nc._active = None

            async def scenario():
                started = await nc.launch("manual")
                self.assertTrue(started["ok"])
                await nc._active
            asyncio.run(scenario())
        stored = json.loads(Path(nc.paths.settings_file()).read_text(encoding="utf-8"))
        self.assertTrue(stored["last_dispatch"]["slot"].startswith("manual:"))
        self.assertEqual(stored["last_dispatch"]["state"], "green")

    def test_scheduler_slot_recorded_and_blocks_same_slot(self):
        cfg = nc.normalize_settings({"enabled": True, "hour": 1, "minute": 0})
        now = datetime(2026, 9, 6, 17, 5, tzinfo=timezone.utc)
        nc._record(cfg, now, "scheduler", nc.slot_of(cfg, now), self.result)
        stored = nc.load_settings()
        self.assertEqual(stored["last_dispatch"]["slot"], "2026-09-07 01:00")
        self.assertFalse(nc.due(stored, now))  # 同槽不重复触发

    def test_launch_rejects_concurrent(self):
        nc._active = None

        async def scenario():
            holder = asyncio.create_task(asyncio.sleep(30))
            nc._active = holder
            second = await nc.launch("manual")
            holder.cancel()
            return second
        second = asyncio.run(scenario())
        self.assertFalse(second["ok"])
        self.assertIn("运行", second["detail"])


if __name__ == "__main__":
    unittest.main()
