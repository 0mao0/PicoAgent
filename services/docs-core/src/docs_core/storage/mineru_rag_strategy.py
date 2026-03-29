import os
import tempfile
import json
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pathlib import Path

# -----------------------------------------------------------------------------
# MinerURag Service Class
# -----------------------------------------------------------------------------

class MinerURag:
    """MinerU RAG 服务"""

    def __init__(self):
        self._rag = None
        self._llm = None

    def _get_rag(self):
        """获取 RAG 构建器"""
        if self._rag is None:
            try:
                from mineru_rag import RAGBuilder
                self._rag = RAGBuilder()
            except ImportError:
                raise ImportError("请安装 mineru-rag: pip install mineru-rag[rag]")
        return self._rag

    def _get_llm(self):
        """获取 LLM 客户端"""
        if self._llm is None:
            try:
                from mineru_rag import LLMClient
                load_dotenv()

                api_key = os.getenv('Public_ALIYUN_API_KEY') or os.getenv('ALIYUN_API_KEY')
                base_url = os.getenv('Public_ALIYUN_API_URL') or os.getenv('ALIYUN_API_URL')
                model = os.getenv('Public_ALIYUN_MODEL2') or os.getenv('ALIYUN_MODEL', 'qwen3.5-397b-a17b')

                self._llm = LLMClient(
                    api_key=api_key,
                    base_url=base_url,
                    model=model
                )
            except ImportError:
                raise ImportError("请安装 mineru-rag: pip install mineru-rag[rag]")
        return self._llm

    def _ensure_vector_store_dir(self, library_id: str) -> Path:
        """确保 MinerU-RAG 的 Faiss 向量库目录存在。"""
        root_dir = Path.home() / '.mineru_rag' / 'vector_db'
        library_dir = root_dir / f'{library_id}_faiss'
        library_dir.mkdir(parents=True, exist_ok=True)
        return library_dir

    def build_knowledge_base(
        self,
        markdown_files: list,
        library_id: str,
        metadata: dict = None
    ) -> Dict[str, Any]:
        """
        构建知识库

        Args:
            markdown_files: Markdown 文件路径列表
            library_id: 知识库 ID
            metadata: 元数据

        Returns:
            构建结果
        """
        rag = self._get_rag()
        self._ensure_vector_store_dir(library_id)

        rag.build_from_files(
            file_paths=markdown_files,
            library_id=library_id,
            metadata=metadata or {}
        )

        return {
            'success': True,
            'library_id': library_id,
            'file_count': len(markdown_files)
        }

    def load_knowledge_base(self, library_id: str) -> None:
        """加载知识库"""
        rag = self._get_rag()
        rag.load_vector_store(library_id=library_id)

    def query(
        self,
        question: str,
        k: int = 4,
        library_id: str = 'default'
    ) -> Dict[str, Any]:
        """
        查询知识库（仅检索）

        Args:
            question: 问题
            k: 检索数量
            library_id: 知识库 ID

        Returns:
            检索结果
        """
        rag = self._get_rag()
        rag.load_vector_store(library_id=library_id)

        result = rag.query(question=question, k=k)

        return {
            'question': question,
            'num_sources': result.get('num_sources', 0),
            'sources': result.get('sources', [])
        }

    def query_with_llm(
        self,
        question: str,
        k: int = 4,
        library_id: str = 'default'
    ) -> Dict[str, Any]:
        """
        查询知识库并使用 LLM 生成答案

        Args:
            question: 问题
            k: 检索数量
            library_id: 知识库 ID

        Returns:
            问答结果
        """
        rag = self._get_rag()
        llm = self._get_llm()

        rag.load_vector_store(library_id=library_id)

        rag_result = rag.query(question=question, k=k)
        answer = llm.query_with_rag(rag_result)

        return {
            'question': question,
            'answer': answer.get('answer', ''),
            'num_sources': answer.get('num_sources', 0),
            'sources': answer.get('sources', [])
        }

# 全局实例
mineru_rag = MinerURag()


# 将主链结构片段投影为 RAG 片段。
def _build_rag_projection_items(structured_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for order_index, item in enumerate(structured_items):
        meta = dict(item.get("meta") or {})
        meta["source_strategy"] = "A_structured"
        meta["projection"] = "rag"
        items.append(
            {
                "id": str(item.get("id") or f"rag-{order_index}"),
                "item_type": "rag_chunk",
                "title": item.get("title") or f"rag_chunk_{order_index}",
                "content": item.get("content") or "",
                "meta": meta,
                "order_index": order_index,
            }
        )
    return items


# 将主链结构片段串联为 RAG 构建器可消费的文本。
def _build_rag_markdown(structured_items: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for item in structured_items:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if title:
            lines.append(f"## {title}")
        if content:
            lines.append(content)
        lines.append("")
    return "\n".join(lines).strip()


# 基于 canonical segments 构建 MinerU-RAG 下游索引。
def build_mineru_rag_index_for_doc(library_id: str, doc_id: str, strategy: str = 'B_mineru_rag') -> Dict[str, Any]:
    from docs_core import knowledge_service

    structured_items = knowledge_service.list_document_segments(doc_id, "A_structured")
    if not structured_items:
        from docs_core.storage.structured_strategy import build_structured_index_for_doc

        build_structured_index_for_doc(library_id, doc_id, "A_structured")
        structured_items = knowledge_service.list_document_segments(doc_id, "A_structured")
    if not structured_items:
        raise ValueError("文档尚无可用 canonical segments")

    items = _build_rag_projection_items(structured_items)
    saved_count = knowledge_service.save_document_segments(doc_id, library_id, strategy, items)
    rag_result: Dict[str, Any] = {'success': False}
    rag_markdown = _build_rag_markdown(structured_items)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as handle:
        handle.write(rag_markdown)
        temp_md = handle.name

    try:
        rag_result = mineru_rag.build_knowledge_base([temp_md], library_id)
    finally:
        try:
            import os
            if os.path.exists(temp_md):
                os.remove(temp_md)
        except Exception:
            pass

    stats = knowledge_service.get_document_segment_stats(doc_id)
    return {'saved_count': saved_count, 'stats': stats, 'rag_result': rag_result}
