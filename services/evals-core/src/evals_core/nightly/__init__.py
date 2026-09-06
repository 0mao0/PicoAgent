"""nightly 全内置流水线：评测→补判→门禁→落盘结论→通知。

真相源在本包（scripts/open_ragbench 的 CLI 是薄壳复用），由 aichat-api 的
内置调度器（services/aichat-api/nightly_control.py）定时或手动触发 pipeline.run_nightly。
"""
