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
from pathlib import Path
from typing import Optional

STATE_GREEN, STATE_RED, STATE_ERROR = "green", "red", "error"
_HEADS = {STATE_GREEN: "**🟢 AnGIneer nightly 评测通过**",
          STATE_RED: "**🔴 AnGIneer nightly 评测回归**",
          STATE_ERROR: "**⚠️ AnGIneer nightly 评测执行失败**"}
_STATE_BY_CONCLUSION = {"success": STATE_GREEN, "failure": STATE_RED}


def _pct(value):
    return f"{value * 100:.2f}%" if isinstance(value, (int, float)) else "—"


def build_message(raw: Optional[dict], gate: Optional[dict], state: str, error_note: str = "") -> str:
    lines = [_HEADS.get(state, _HEADS[STATE_ERROR])]
    summary = (raw or {}).get("summary_scores") or {}
    if summary:
        lines.append(
            f"> run `{(raw or {}).get('run_id', '?')}`：**{_pct(summary.get('overall_score'))}**"
            f"（正确 {summary.get('correct', '?')}/{summary.get('total', '?')}），"
            f"错误 {summary.get('errored', 0)}，judge 异常 {summary.get('judge_failed_count', '?')}"
            f"｜检索 {_pct(summary.get('retrieval_score'))}｜答案 {_pct(summary.get('answer_score'))}"
        )
    if gate:
        m = gate.get("matrix") or {}
        delta, ci = gate.get("delta"), gate.get("delta_ci95")
        lines.append(
            f"> vs 基线「{gate.get('base_label', '?')}」：Δ"
            f"{(f'{delta * 100:+.2f}pp' if isinstance(delta, (int, float)) else '—')}"
            + (f"（95%CI [{ci[0] * 100:+.2f}, {ci[1] * 100:+.2f}]pp）" if ci else "")
            + f"｜矩阵 双过{m.get('pp', '?')}·修复{m.get('pf', '?')}·回退{m.get('fp', '?')}·双挂{m.get('ff', '?')}"
        )
        regressions = list((gate.get("regressions") or {}).items())[:5]
        if regressions:
            lines.append("> 回退样例：" + "；".join(f"`{q[:8]}` {b}" for q, b in regressions))
        for reason in (gate.get("gate_reasons") or [])[:3]:
            lines.append(f"> 🔺 {reason}")
    if state == STATE_ERROR:
        lines.append(f"> 上游环节未完成，无门禁结论。信息：{error_note or '见工作流日志'}")
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
        text += f"\n> [查看完整日志与产物]({args.run_url})"
    webhook = os.environ.get("WEBHOOK", "").strip()
    if not webhook:
        print("WEBHOOK 未配置，跳过推送:\n" + text)
        return 0
    print(send(webhook, text))
    return 0  # 通知本身失败与否不翻转 job 结论（结论由 gate/fail-on-red 步骤决定）


if __name__ == "__main__":
    sys.exit(main())
