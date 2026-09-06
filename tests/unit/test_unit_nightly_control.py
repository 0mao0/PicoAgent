"""nightly_control 单测：配置校验/持久化、下次触发与到点判定（北京时间）、GitHub dispatch。"""
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

BJT = ZoneInfo("Asia/Shanghai")


class _TmpSettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "nightly_settings.json")
        patch = mock.patch.dict(os.environ, {"NIGHTLY_SETTINGS_FILE": self.path})
        patch.start()
        self.addCleanup(patch.stop)


class DefaultPathTests(unittest.TestCase):
    """未设 NIGHTLY_SETTINGS_FILE 时必须走 result_store 同目录（服务器真实路径）。"""

    def test_default_path_follows_result_store(self):
        from evals_core.storage import result_store
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(result_store, "_DB_PATH", str(Path(td) / "evals" / "evals.sqlite")):
                got = nc.settings_file()
            self.assertEqual(str(got), str(Path(td) / "evals" / "nightly_settings.json"))


class SettingsTests(_TmpSettings):
    def test_load_defaults_when_missing(self):
        cfg = nc.load_settings()
        self.assertEqual(cfg["enabled"], False)
        self.assertEqual((cfg["hour"], cfg["minute"]), (1, 0))
        self.assertIsNone(cfg["last_dispatch"])

    def test_save_and_reload_roundtrip(self):
        nc.save_settings({"enabled": True, "hour": 2, "minute": 30})
        cfg = nc.load_settings()
        self.assertEqual(cfg, {"enabled": True, "hour": 2, "minute": 30, "last_dispatch": None})

    def test_normalize_validation(self):
        self.assertEqual(nc.normalize_settings({"enabled": True, "hour": 23, "minute": 59}),
                         {"enabled": True, "hour": 23, "minute": 59})
        for bad in ({"hour": 24}, {"hour": -1}, {"minute": 60}, {"hour": "x"}, "not-dict", {"enabled": "yes"}):
            with self.assertRaises(ValueError):
                nc.normalize_settings(bad)

    def test_load_tolerates_corrupt_file(self):
        Path(self.path).write_text("{坏 json", encoding="utf-8")
        self.assertEqual(nc.load_settings()["enabled"], False)


class FireTimeTests(unittest.TestCase):
    def test_disabled_no_fire(self):
        now = datetime(2026, 9, 6, 4, 0, tzinfo=timezone.utc)
        self.assertIsNone(nc.next_fire_at({"enabled": False, "hour": 1, "minute": 0}, now))

    def test_next_fire_uses_beijing_time(self):
        # UTC 09:00 = 北京 17:00；设 01:00 → 次日北京 01:00（= 当日 UTC 17:00）
        now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
        nxt = nc.next_fire_at({"enabled": True, "hour": 1, "minute": 0}, now)
        self.assertEqual(nxt.astimezone(BJT).strftime("%Y-%m-%d %H:%M"), "2026-09-07 01:00")

    def test_next_fire_today_when_still_future(self):
        now = datetime(2026, 9, 6, 23, 30, tzinfo=timezone.utc)  # 北京 07-07 07:30
        nxt = nc.next_fire_at({"enabled": True, "hour": 23, "minute": 0}, now)
        self.assertEqual(nxt.astimezone(BJT).strftime("%Y-%m-%d %H:%M"), "2026-09-07 23:00")

    def test_due_gate(self):
        cfg = {"enabled": True, "hour": 1, "minute": 0}
        before = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)   # 北京 00:00
        after = datetime(2026, 9, 6, 17, 5, tzinfo=timezone.utc)    # 北京 01:05
        self.assertFalse(nc.due(cfg, before))
        self.assertTrue(nc.due(cfg, after))
        dispatched = dict(cfg, last_dispatch={"slot": nc.slot_of(cfg, after)})
        self.assertFalse(nc.due(dispatched, after))                  # 同槽幂等
        self.assertFalse(nc.due(dict(cfg, enabled=False), after))


class DispatchTests(_TmpSettings):
    def test_missing_token_fails_soft(self):
        with mock.patch.dict(os.environ, {"NIGHTLY_GH_TOKEN": ""}):
            result = nc.dispatch_github("manual")
        self.assertFalse(result["ok"])
        self.assertIn("TOKEN", result["detail"])

    def test_dispatch_success_records_dispatch(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.status = 204
        with mock.patch.dict(os.environ, {"NIGHTLY_GH_TOKEN": "ghp_test"}), \
             mock.patch("nightly_control.urllib.request.urlopen", return_value=fake) as urlopen:
            result = nc.dispatch_github("scheduler")
        self.assertTrue(result["ok"])
        self.assertIn("/workflows/eval-nightly.yml/dispatches", urlopen.call_args[0][0].full_url)
        cfg = nc.record_dispatch(nc.load_settings(), datetime(2026, 9, 6, 17, 5, tzinfo=timezone.utc),
                                 "scheduler", result)
        stored = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.assertEqual(stored["last_dispatch"]["slot"], "2026-09-07 01:00")  # 北京日期+配置时刻
        self.assertTrue(cfg["last_dispatch"]["ok"])

    def test_manual_slot_never_blocks_scheduler(self):
        now = datetime(2026, 9, 6, 17, 5, tzinfo=timezone.utc)
        cfg = nc.record_dispatch({"enabled": True, "hour": 1, "minute": 0}, now, "manual", {"ok": True})
        self.assertTrue(str(cfg["last_dispatch"]["slot"]).startswith("manual:"))
        self.assertTrue(nc.due(cfg, now))  # manual 记录不占用调度槽位


if __name__ == "__main__":
    unittest.main()
