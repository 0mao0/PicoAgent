"""执行层内部协议。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from docs_core.query.contracts import RetrievedItem, SqlPayload


@dataclass
class ExecutorResult:
    """统一执行结果。"""

    candidates: List[RetrievedItem]
    pre_filter_candidates: List[RetrievedItem] = field(default_factory=list)
    dense_candidates: List[RetrievedItem] = field(default_factory=list)
    sparse_candidates: List[RetrievedItem] = field(default_factory=list)
    fusion_debug: Dict[str, Any] = field(default_factory=dict)
    retrieval_route: str = "content_hybrid"
    fallback_used: bool = False
    evidence_sufficient: bool = True
    sql_payload: Optional[SqlPayload] = None
    answer: str = ""
    confidence: float = 0.0
    extra_debug: Dict[str, Any] = field(default_factory=dict)
