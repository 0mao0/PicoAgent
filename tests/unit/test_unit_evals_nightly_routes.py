"""夜间维护只读接口测试：鉴权（401/403）、列表/详情、日期防穿越、损坏目录降级。"""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for rel in (
    "services/aichat-api",
    "services/evals-core/src",
    "services/angineer-core/src",
    "services/ai-inference/src",
    "services/sop-core/src",
):
    p = os.path.join(ROOT, rel)
    if p not in sys.path:
        sys.path.insert(0, p)

# chat_auth 依赖 models.user（docs-api 侧）——测试里用桩模块顶掉，只测路由与鉴权装配本身
_chat_auth_stub = types.ModuleType("chat_auth")
_chat_auth_stub.resolve_session_principal = lambda request: False
sys.modules.setdefault("chat_auth", _chat_auth_stub)

import evals_routes  # noqa: E402


class _Principal:
    def __init__(self, is_admin):
        self.is_admin = is_admin
        self.is_active = True
        self.library_ids = []


def _patch_auth(is_authenticated: bool, is_admin: bool = False):
    def _resolve(request):
        if not is_authenticated:
            return False
        request.state.session_user = _Principal(is_admin)
        return True
    return mock.patch.object(evals_routes, "resolve_session_principal", side_effect=_resolve)


class NightlyRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.eval_dir = Path(self.tmp.name) / "evals"
        self.eval_dir.mkdir()
        self.nightly = self.eval_dir / "nightly"
        self.nightly.mkdir()
        self.db_patch = mock.patch.object(evals_routes.result_store, "_DB_PATH",
                                          str(self.eval_dir / "evals.sqlite"))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(evals_routes.evals_router, prefix="/api/evals")
        return TestClient(app, base_url="http://test")

    def _write_day(self, date: str, payload, raw_text=None):
        day = self.nightly / date
        day.mkdir()
        (day / "nightly.json").write_text(
            json.dumps(payload) if raw_text is None else raw_text, encoding="utf-8")
        (day / "report.md").write_text("# 报告\n门禁 GREEN", encoding="utf-8")
        return day

    DAY = {"state": "green", "overall_score": 0.8768, "correct": 427, "total": 487,
           "delta": 0.0267, "base_label": "R2", "matrix": {"pp": 396, "pf": 31, "fp": 18, "ff": 42}}

    def test_requires_session_401(self):
        with _patch_auth(False):
            r = self._client().get("/api/evals/nightly")
        self.assertEqual(r.status_code, 401)

    def test_non_admin_403(self):
        with _patch_auth(True, is_admin=False):
            r = self._client().get("/api/evals/nightly")
        self.assertEqual(r.status_code, 403)

    def test_list_desc_and_corrupt_degrade(self):
        self._write_day("2026-09-05", self.DAY)
        self._write_day("2026-09-06", self.DAY)
        self._write_day("2026-09-07", None, raw_text="{坏 json")
        with _patch_auth(True, is_admin=True):
            r = self._client().get("/api/evals/nightly")
        self.assertEqual(r.status_code, 200)
        days = r.json()["days"]
        self.assertEqual([d["date"] for d in days], ["2026-09-07", "2026-09-06", "2026-09-05"])
        self.assertEqual(days[0]["state"], "corrupt")       # 损坏目录不炸全局
        self.assertEqual(days[1]["overall_score"], 0.8768)

    def test_detail_returns_report_md(self):
        self._write_day("2026-09-06", self.DAY)
        with _patch_auth(True, is_admin=True):
            r = self._client().get("/api/evals/nightly/2026-09-06")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nightly"]["delta"], 0.0267)
        self.assertIn("门禁 GREEN", r.json()["report_md"])

    def test_traversal_and_missing_404(self):
        with _patch_auth(True, is_admin=True):
            c = self._client()
            self.assertEqual(c.get("/api/evals/nightly/..%2F..%2Fetc").status_code, 404)
            self.assertEqual(c.get("/api/evals/nightly/2026-9-6").status_code, 404)   # 格式不合法
            self.assertEqual(c.get("/api/evals/nightly/2026-09-01").status_code, 404)  # 无该日

    def test_missing_root_returns_empty(self):
        import shutil
        shutil.rmtree(self.nightly)
        with _patch_auth(True, is_admin=True):
            r = self._client().get("/api/evals/nightly")
        self.assertEqual(r.json(), {"days": []})

    # ---- 调度配置接口（GET/PUT settings、POST run-now）----

    def _settings_env(self):
        import nightly_control  # noqa: F401  同一模块对象，patch 才对路由生效
        return mock.patch.dict(os.environ,
                               {"NIGHTLY_SETTINGS_FILE": str(self.eval_dir / "nightly_settings.json")})

    def test_settings_requires_admin(self):
        with self._settings_env(), _patch_auth(False):
            self.assertEqual(self._client().get("/api/evals/nightly/settings").status_code, 401)
        with self._settings_env(), _patch_auth(True, is_admin=False):
            r = self._client().put("/api/evals/nightly/settings", json={"enabled": True, "hour": 1, "minute": 0})
            self.assertEqual(r.status_code, 403)

    def test_settings_default_put_validation_persist(self):
        settings_file = self.eval_dir / "nightly_settings.json"
        with self._settings_env(), _patch_auth(True, is_admin=True):
            c = self._client()
            r = c.get("/api/evals/nightly/settings")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["enabled"], False)
            self.assertIsNone(r.json()["next_fire_at"])          # 未启用 → 无下次触发
            r = c.put("/api/evals/nightly/settings", json={"enabled": True, "hour": 2, "minute": 30})
            self.assertTrue(r.json()["enabled"])
            self.assertIsNotNone(r.json()["next_fire_at"])        # 启用后必有下次触发时刻
            self.assertIn('"hour": 2', settings_file.read_text(encoding="utf-8"))
            self.assertEqual(c.put("/api/evals/nightly/settings", json={"hour": 24}).status_code, 400)

    def test_run_now_dispatches_manual(self):
        import nightly_control
        settings_file = self.eval_dir / "nightly_settings.json"
        with self._settings_env(), \
             mock.patch.object(nightly_control, "dispatch_github", return_value={"ok": True, "detail": ""}) as dispatched, \
             _patch_auth(True, is_admin=True):
            r = self._client().post("/api/evals/nightly/run-now")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(dispatched.call_args[0][0], "manual")
        stored = json.loads(settings_file.read_text(encoding="utf-8"))
        self.assertEqual(stored["last_dispatch"]["source"], "manual")


if __name__ == "__main__":
    unittest.main()
