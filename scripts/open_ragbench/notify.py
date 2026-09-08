"""nightly 结果 → 企微卡片（CLI 薄壳；卡片构建真相源在 evals_core.nightly.notify）。

三态严格区分：绿色必须有门禁结论背书，缺一律 error（nightly 首跑实踩）。
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from open_ragbench import common  # noqa: F401  统一 sys.path 引导（evals-core 可导入）
from evals_core.nightly import notify as _notify
from shared.notify import send as _send

STATE_GREEN, STATE_RED, STATE_ERROR = _notify.STATE_GREEN, _notify.STATE_RED, _notify.STATE_ERROR
build_message = _notify.build_message
_STATE_BY_CONCLUSION = {"success": STATE_GREEN, "failure": STATE_RED}


def main() -> int:
    parser = argparse.ArgumentParser(description="nightly 结果推送企微（三态：green/red/error）")
    parser.add_argument("--raw", default="", help="评测全量结果 json（可缺失）")
    parser.add_argument("--gate", default="", help="门禁结论 json（可缺失）")
    parser.add_argument("--gate-state", default="skipped", help="门禁 step conclusion：success/failure/skipped")
    parser.add_argument("--error-note", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--site-url", default="", help="站点夜间维护视图地址（缺省时只给运行日志链接）")
    args = parser.parse_args()

    state = _STATE_BY_CONCLUSION.get(args.gate_state, STATE_ERROR)

    def _load(path):
        if not path:
            return None
        try:
            return common.load_json(Path(path))
        except (OSError, ValueError):
            return None

    raw, gate = _load(args.raw), _load(args.gate)
    if state == STATE_GREEN and not gate:
        state = STATE_ERROR  # 绿色必须有门禁结论背书，缺了就按执行失败报
    note = args.error_note
    if state == STATE_ERROR and not note and raw is None:
        note = "未产出评测结果文件（评测环节可能中途失败；后端 run 可能仍在执行，可查 evals 库）"
    text = build_message(raw, gate, state, note)
    if args.site_url and args.run_url:
        text += f"\n查看：[夜间维护]({args.site_url})｜[运行日志]({args.run_url})"
    elif args.site_url:
        text += f"\n查看：[夜间维护]({args.site_url})"
    elif args.run_url:
        text += f"\n查看：[运行日志]({args.run_url})"
    webhook_system = os.environ.get("WEBHOOK_SYSTEM", "").strip()
    webhook_owner = os.environ.get("WEBHOOK_OWNER", "").strip()
    webhooks = [w for w in [webhook_system, webhook_owner] if w]
    webhook = ",".join(webhooks)
    if not webhook:
        print("WEBHOOK_SYSTEM/WEBHOOK_OWNER 均未配置，跳过推送:\n" + text)
        return 0
    print(_send(webhook, text, quiet=True))
    return 0  # 通知本身失败与否不翻转 job 结论（结论由 gate 决定）


if __name__ == "__main__":
    sys.exit(main())
