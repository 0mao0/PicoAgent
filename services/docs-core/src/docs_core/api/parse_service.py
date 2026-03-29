"""文档解析编排服务。"""
import shutil
import tempfile
import threading
import traceback
import uuid
from typing import Any, Dict, Optional

from docs_core import file_storage, mineru_parser
from docs_core.api.knowledge_api import knowledge_service
from docs_core.storage.structured_strategy import build_structured_index_for_doc


class ParseOrchestrator:
    """负责 API 层与解析主链之间的编排。"""

    def __init__(self) -> None:
        self._threads: Dict[str, threading.Thread] = {}

    # 注册或补全文档节点，确保解析主链使用统一文档标识。
    def ensure_document(self, library_id: str, file_path: str, doc_id: Optional[str] = None) -> str:
        node = knowledge_service.register_document(library_id=library_id, file_path=file_path, doc_id=doc_id)
        return node.id

    # 创建解析任务并启动后台线程。
    def create_parse_task(self, library_id: str, doc_id: str, file_path: str) -> Dict[str, Any]:
        task_id = f"parse-{uuid.uuid4().hex[:12]}"
        task = knowledge_service.create_parse_task(task_id, library_id, doc_id)
        knowledge_service.update_node(
            doc_id,
            status="processing",
            parse_progress=0,
            parse_stage="queued",
            parse_error=None,
            parse_task_id=task_id,
        )
        worker = threading.Thread(
            target=self._run_parse_task,
            args=(task_id, library_id, doc_id, file_path),
            daemon=True,
            name=f"parse-task-{task_id}",
        )
        self._threads[task_id] = worker
        worker.start()
        return {
            "task_id": task.id,
            "doc_id": doc_id,
            "status": task.status,
            "progress": task.progress,
            "stage": task.stage,
        }

    # 返回当前任务状态。
    def get_parse_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = knowledge_service.get_parse_task(task_id)
        if not task:
            return None
        return task.model_dump(mode="json")

    # 在后台执行文档解析并同步状态。
    def _run_parse_task(self, task_id: str, library_id: str, doc_id: str, file_path: str) -> None:
        temp_output_dir = tempfile.mkdtemp(prefix=f"parse-{doc_id}-")
        try:
            self._update_progress(task_id, doc_id, status="processing", progress=5, stage="preparing")
            source_path = file_storage.ensure_doc_source_file(library_id, doc_id, file_path=file_path)
            if not source_path:
                raise RuntimeError("源文件不存在或无法复制到规范目录")

            self._update_progress(task_id, doc_id, progress=20, stage="parsing")
            parse_result = mineru_parser.parse_document(input_path=source_path, output_dir=temp_output_dir)
            if not parse_result.get("success"):
                raise RuntimeError(parse_result.get("error") or "MinerU 解析失败")

            markdown_path = parse_result.get("md_file")
            if markdown_path:
                with open(markdown_path, "r", encoding="utf-8") as handle:
                    file_storage.save_markdown(library_id, doc_id, handle.read())
            file_storage.save_parse_artifacts(library_id, doc_id, temp_output_dir)

            self._update_progress(task_id, doc_id, progress=70, stage="indexing")
            build_structured_index_for_doc(
                library_id=library_id,
                doc_id=doc_id,
                strategy="A_structured",
                options={"use_llm": True},
            )

            self._update_progress(task_id, doc_id, progress=100, stage="completed", status="completed")
        except Exception as exc:
            error_message = f"{exc}\n{traceback.format_exc()}"
            knowledge_service.update_parse_task(
                task_id,
                status="failed",
                progress=100,
                stage="failed",
                error=error_message,
            )
            knowledge_service.update_node(
                doc_id,
                status="failed",
                parse_progress=100,
                parse_stage="failed",
                parse_error=error_message,
                parse_task_id=task_id,
            )
        finally:
            self._threads.pop(task_id, None)
            shutil.rmtree(temp_output_dir, ignore_errors=True)

    # 同步更新任务和节点的解析进度。
    def _update_progress(
        self,
        task_id: str,
        doc_id: str,
        progress: int,
        stage: str,
        status: str = "processing",
    ) -> None:
        knowledge_service.update_parse_task(task_id, status=status, progress=progress, stage=stage, error=None)
        knowledge_service.update_node(
            doc_id,
            status="completed" if status == "completed" else "processing",
            parse_progress=progress,
            parse_stage=stage,
            parse_error=None,
            parse_task_id=task_id,
        )


parse_orchestrator = ParseOrchestrator()
