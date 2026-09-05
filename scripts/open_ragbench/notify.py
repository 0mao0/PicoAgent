"""nightly 结果 → 企微卡片。三态严格区分（nightly 首跑实踩：评测步骤中途炸了、
门禁产物不存在，旧内联脚本却把"未获取到 gate.json"渲染成绿色"评测通过"）：

- green：门禁通过；red：门禁红线；error：评测/报告/门禁任一环节没跑成（绝不显示"通过"）。

卡片必须带真实结果（run 分数、异常数、检索/答案分）与基线差异（Δpp+CI、过渡矩阵、
回退样例）——用户视角是"测试集重新跑一遍的结果和与基线的区别"，不是一句"通过"。
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

STATE_GREEN, STATE_RED, STATE_ERROR = "green", "red", "error"
_HEADS = {STATE_GREEN: "**🟢 AnGIneer nightly 评测通过**",
          STATE_RED: "**🔴 AnGIneer nightly 评测回归**",
          STATE_ERROR: "**⚠️ AnGIneer nightly 评测执行失败**"}
_STATE_BY_CONCLUSION = {"success": STATE_GREEN, "failure": STATE_RED}


def _pct(value):
    return f"{value * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def _fmt_span(started_at, completed_at) -> Tuple[str, str]:
    """run 起止（容器 UTC → 北京时间）与时长。字段缺失一律 '—'，通知不许造时间。"""
    try:
        start = datetime.fromisoformat(str(started_at)) + timedelta(hours=8)
        end = datetime.fromisoformat(str(completed_at)) + timedelta(hours=8)
        minutes = max(0, int((end - start).total_seconds() // 60))
        span = f"{start:%m-%d %H:%M} – {end:%H:%M}"
        duration = f"{minutes // 60}h{minutes % 60:02d}m"
        return span, duration
    except (TypeError, ValueError):
        return "—", "—"


def build_message(raw: Optional[dict], gate: Optional[dict], state: str, error_note: str = "") -> str:
    """一行一项：时间 / 时长 / 结果 / 分析 /（回退样例）/ 查看。"""
    summary = (raw or {}).get("summary_scores") or {}
    span, duration = _fmt_span((raw or {}).get("started_at"), (raw or {}).get("completed_at"))
    lines = [_HEADS.get(state, _HEADS[STATE_ERROR])]
    lines.append(f"时间：{span}（北京时间）")
    lines.append(f"时长：{duration}")
    if summary:
        lines.append(
            f"结果：**{_pct(summary.get('overall_score'))}**"
            f"（正确 {summary.get('correct', '?')}/{summary.get('total', '?')}）"
            f"｜judge 异常 {summary.get('judge_failed_count', '?')}"
            f"｜执行错误 {summary.get('errored', 0)}"
        )
    else:
        lines.append("结果：—（未产出评测结果）")
    if gate:
        m = gate.get("matrix") or {}
        delta, ci = gate.get("delta"), gate.get("delta_ci95")
        delta_s = f"Δ{delta * 100:+.2f}pp" if isinstance(delta, (int, float)) else "Δ—"
        ci_s = f"（CI [{ci[0] * 100:+.2f},{ci[1] * 100:+.2f}]pp）" if ci else ""
        net = (m.get("pf", 0) - m.get("fp", 0)) if "pf" in m and "fp" in m else None
        trend = ("净提升" if (net or 0) > 0 else ("净回退" if (net or 0) < 0 else "持平")) if net is not None else ""
        verdict = "显著回退" if state == STATE_RED else "无显著回退"
        lines.append(
            f"分析：vs「{gate.get('base_label', '?')}」{delta_s}{ci_s}"
            f"｜修复{m.get('pf', '?')}·回退{m.get('fp', '?')}·双过{m.get('pp', '?')}"
            + (f" → {trend} {net:+d} 题，{verdict}" if net is not None else "")
        )
        for reason in (gate.get("gate_reasons") or [])[:2]:
            lines.append(f"⚠ {reason}")
        regressions = list((gate.get("regressions") or {}).items())[:5]
        if regressions:
            lines.append("样例：" + "；".join(f"`{q[:8]}` {b}" for q, b in regressions))
    elif state != STATE_ERROR:
        lines.append("分析：—（门禁产物缺失）")
    else:
        lines.append(f"分析：{error_note or '见工作流日志'}")
    return "\n".join(lines)


def send(webhook: str, text: str) -> str:
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": text}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser(description="nightly 结果推送企微（三态：green/red/error）")
    parser.add_argument("--raw", default="", help="评测全量结果 json（可缺失）")
    parser.add_argument("--gate", default="", help="compare_runs 门禁 json（可缺失）")
    parser.add_argument("--gate-state", default="skipped", help="门禁 step conclusion：success/failure/skipped")
    parser.add_argument("--error-note", default="")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()

    state = _STATE_BY_CONCLUSION.get(args.gate_state, STATE_ERROR)
    def _load(path):
        if not path:
            return None
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    raw, gate = _load(args.raw), _load(args.gate)
    if state == STATE_GREEN and not gate:
        state = STATE_ERROR  # 绿色必须有门禁产物背书，缺了就按执行失败报
    note = args.error_note
    if state == STATE_ERROR and not note and raw is None:
        note = "未产出评测结果文件（评测步骤可能中途失败；后端 run 可能仍在执行，可查 evals 库）"
    text = build_message(raw, gate, state, note)
    if args.run_url:
        text += f"\n查看：[日志与产物]({args.run_url})"
    webhook = os.environ.get("WEBHOOK", "").strip()
    if not webhook:
        print("WEBHOOK 未配置，跳过推送:\n" + text)
        return 0
    print(send(webhook, text))
    return 0  # 通知本身失败与否不翻转 job 结论（结论由 gate/fail-on-red 步骤决定）


if __name__ == "__main__":
    sys.exit(main())
