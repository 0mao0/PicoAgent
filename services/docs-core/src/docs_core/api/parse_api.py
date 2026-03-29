"""文档解析 API。"""
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from docs_core.api.parse_service import parse_orchestrator
from docs_core.storage.structured_strategy import build_structured_index_for_doc, get_doc_blocks_graph


router = APIRouter()


class KnowledgeParseRequest(BaseModel):
    """文档解析请求。"""

    library_id: str
    doc_id: str
    file_path: Optional[str] = None


class KnowledgeStructuredIndexRequest(BaseModel):
    """结构化索引重建请求。"""

    library_id: str
    doc_id: str
    strategy: Optional[str] = "A_structured"


class DocBlocksGraphRequest(BaseModel):
    """文档块图谱请求。"""

    library_id: str
    doc_id: str


# 按策略分发结构化索引构建。
def _build_projection_for_doc(library_id: str, doc_id: str, strategy: str = "A_structured") -> Dict[str, Any]:
    if strategy == "A_structured":
        return build_structured_index_for_doc(library_id, doc_id, strategy)
    if strategy == "B_mineru_rag":
        from docs_core.storage.mineru_rag_strategy import build_mineru_rag_index_for_doc

        return build_mineru_rag_index_for_doc(library_id, doc_id, strategy)
    if strategy == "C_pageindex":
        from docs_core.storage.pageindex_strategy import build_pageindex_for_doc

        return build_pageindex_for_doc(library_id, doc_id, strategy)
    raise ValueError(f"Unsupported strategy: {strategy}")


# 创建解析任务并交给编排层执行。
@router.post("/parse")
async def create_parse_task(request: KnowledgeParseRequest) -> Dict[str, Any]:
    """创建文档解析任务。"""

    if not request.file_path:
        raise HTTPException(status_code=400, detail="缺少文档文件路径")
    source_path = Path(request.file_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="源文件不存在")

    doc_id = parse_orchestrator.ensure_document(
        library_id=request.library_id,
        file_path=str(source_path),
        doc_id=request.doc_id,
    )
    return parse_orchestrator.create_parse_task(
        library_id=request.library_id,
        doc_id=doc_id,
        file_path=str(source_path),
    )


# 查询解析任务状态。
@router.get("/parse/tasks/{task_id}")
@router.get("/parse/{task_id}", include_in_schema=False)
async def get_parse_status(task_id: str) -> Dict[str, Any]:
    """获取解析任务状态。"""

    task = parse_orchestrator.get_parse_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# 手动重建指定文档的策略投影。
@router.post("/parse/structured-index")
async def build_structured_index(request: KnowledgeStructuredIndexRequest) -> Dict[str, Any]:
    """重建结构化索引。"""

    try:
        result = _build_projection_for_doc(request.library_id, request.doc_id, request.strategy or "A_structured")
        return {"status": "success", "data": result}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


# 获取文档的块图谱视图。
@router.post("/parse/doc-blocks-graph")
async def get_doc_blocks_graph_view(request: DocBlocksGraphRequest) -> Dict[str, Any]:
    """获取文档块图谱数据。"""

    try:
        graph = get_doc_blocks_graph(request.library_id, request.doc_id)
        if not graph:
            raise HTTPException(status_code=404, detail="Graph data not found. Please run structured-index first.")
        return {"status": "success", "data": graph}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
