"""知识回答评测脚本薄入口。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_CORE_SRC = PROJECT_ROOT / "services" / "docs-core" / "src"

sys.path.insert(0, str(DOCS_CORE_SRC))

from docs_core.evals.eval_answer import main


if __name__ == "__main__":
    main()
