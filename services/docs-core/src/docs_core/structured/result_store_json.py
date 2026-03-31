"""结构化结果文件与 JSON 存储。"""
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docs_core.structured.mineru_to_a1 import (
    A1StructureResult,
    build_a1_from_mineru,
)
from docs_core.structured.result_store_db import persist_doc_blocks


class FileStorage:
    """文件存储管理器。"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            root_dir = Path(__file__).resolve().parents[5]
            base_dir = str(root_dir / "data" / "knowledge_base")

        self.base_dir = Path(base_dir)
        self.libraries_dir = self.base_dir / "libraries"

        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在。"""
        self.libraries_dir.mkdir(parents=True, exist_ok=True)

    def _library_root(self, library_id: str) -> Path:
        library_root = self.libraries_dir / library_id
        library_root.mkdir(parents=True, exist_ok=True)
        return library_root

    def get_doc_root(self, library_id: str, doc_id: str) -> Path:
        """获取一文档一目录根路径。"""
        doc_root = self._library_root(library_id) / "documents" / doc_id
        doc_root.mkdir(parents=True, exist_ok=True)
        return doc_root

    def get_source_dir(self, library_id: str, doc_id: str) -> Path:
        """获取源文件目录。"""
        source_dir = self.get_doc_root(library_id, doc_id) / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        return source_dir

    def get_parsed_dir(self, library_id: str, doc_id: str) -> Path:
        """获取解析结果目录。"""
        parsed_dir = self.get_doc_root(library_id, doc_id) / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        return parsed_dir

    def get_graph_path(self, library_id: str, doc_id: str) -> Path:
        """获取结构图谱文件路径。"""
        return self.get_parsed_dir(library_id, doc_id) / "doc_blocks_graph.json"

    def get_edited_dir(self, library_id: str, doc_id: str) -> Path:
        """获取编辑目录。"""
        edited_dir = self.get_doc_root(library_id, doc_id) / "edited"
        edited_dir.mkdir(parents=True, exist_ok=True)
        return edited_dir

    def get_raw_dir(self, library_id: str, doc_id: str) -> Path:
        """获取解析原始返回目录。"""
        raw_dir = self.get_parsed_dir(library_id, doc_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir

    def get_mineru_raw_dir(self, library_id: str, doc_id: str) -> Path:
        """获取 MinerU 原始结构目录。"""
        raw_dir = self.get_parsed_dir(library_id, doc_id) / "mineru_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir

    def get_parsed_markdown_path(self, library_id: str, doc_id: str) -> Path:
        """获取解析 Markdown 路径。"""
        return self.get_parsed_dir(library_id, doc_id) / "content.md"

    def get_middle_json_path(self, library_id: str, doc_id: str) -> Path:
        """获取中间语义数据文件路径。"""
        return self.get_parsed_dir(library_id, doc_id) / "middle.json"

    def get_edited_markdown_path(self, library_id: str, doc_id: str) -> Path:
        """获取新版编辑 Markdown 路径。"""
        return self.get_edited_dir(library_id, doc_id) / "current.md"

    def save_source_file(
        self,
        library_id: str,
        doc_id: str,
        content: bytes,
        original_filename: Optional[str] = None,
    ) -> str:
        """保存源文件。"""
        safe_name = Path(original_filename or f"{doc_id}.pdf").name
        source_path = self.get_source_dir(library_id, doc_id) / safe_name
        with open(source_path, "wb") as f:
            f.write(content)
        return str(source_path)

    def save_markdown(self, library_id: str, doc_id: str, content: str) -> str:
        """保存 Markdown 文件。"""
        parsed_md_path = self.get_parsed_markdown_path(library_id, doc_id)
        with open(parsed_md_path, "w", encoding="utf-8") as f:
            f.write(content)
        edited_md_path = self.get_edited_markdown_path(library_id, doc_id)
        if not edited_md_path.exists():
            with open(edited_md_path, "w", encoding="utf-8") as f:
                f.write(content)
        return str(parsed_md_path)

    def save_edited_markdown(self, library_id: str, doc_id: str, content: str) -> str:
        """保存编辑后的 Markdown 文件。"""
        edited_dir = self.get_edited_dir(library_id, doc_id)
        current_path = edited_dir / "current.md"
        with open(current_path, "w", encoding="utf-8") as f:
            f.write(content)
        revision_dir = edited_dir / "history"
        revision_dir.mkdir(parents=True, exist_ok=True)
        revision_path = revision_dir / f'{datetime.now().strftime("%Y%m%d%H%M%S")}.md'
        with open(revision_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(current_path)

    def save_parse_artifacts(self, library_id: str, doc_id: str, output_dir: str) -> Dict[str, Any]:
        """保存解析产物到文档目录。"""
        parsed_dir = self.get_parsed_dir(library_id, doc_id)
        if not parsed_dir.exists():
            parsed_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(output_dir, parsed_dir, dirs_exist_ok=True)

        mineru_raw_dir = self.get_mineru_raw_dir(library_id, doc_id)

        for pdf_file in list(parsed_dir.rglob("*.pdf")):
            try:
                pdf_file.unlink()
            except Exception:
                pass

        artifact_map = {
            "origin.zip": "origin.zip",
            "*model.json": "model.json",
            "layout.json": "layout.json",
            "*content_list_v2.json": "content_list_v2.json",
            "*_content_list.json": "content_list.json",
        }

        final_files = {}
        for pattern, target_name in artifact_map.items():
            found_files = list(parsed_dir.rglob(pattern))
            for artifact_file in found_files:
                if target_name == "content_list.json" and artifact_file.name == "content_list_v2.json":
                    continue
                target = mineru_raw_dir / target_name
                try:
                    if artifact_file.resolve() != target.resolve():
                        if target.exists():
                            target.unlink()
                        shutil.move(str(artifact_file), str(target))
                    final_files[target_name] = str(target)
                except Exception:
                    pass

        assets_path = parsed_dir / "assets"
        images_path = parsed_dir / "images"
        if assets_path.exists() and images_path.exists():
            try:
                shutil.rmtree(assets_path)
            except Exception:
                pass

        return final_files

    def save_assets(self, library_id: str, doc_id: str, source_dir: str) -> str:
        """保存解析产物中的资产文件目录。"""
        assets_path = self.get_parsed_dir(library_id, doc_id) / "assets"
        if assets_path.exists():
            shutil.rmtree(assets_path)
        if os.path.isdir(source_dir):
            shutil.copytree(source_dir, assets_path)
        else:
            assets_path.mkdir(parents=True, exist_ok=True)
        return str(assets_path)

    def save_raw_artifacts(self, library_id: str, doc_id: str, source_dir: str) -> str:
        """保存解析流程中的原始返回文件目录。"""
        raw_path = self.get_raw_dir(library_id, doc_id)
        if raw_path.exists():
            shutil.rmtree(raw_path)
        if os.path.isdir(source_dir):
            shutil.copytree(source_dir, raw_path)
        else:
            raw_path.mkdir(parents=True, exist_ok=True)
        return str(raw_path)

    def resolve_canonical_raw_dir(self, library_id: str, doc_id: str) -> Path:
        """解析结构主链应优先读取的原始目录。"""
        mineru_raw_dir = self.get_parsed_dir(library_id, doc_id) / "mineru_raw"
        if mineru_raw_dir.exists():
            return mineru_raw_dir
        return self.get_parsed_dir(library_id, doc_id)

    def get_mineru_blocks_path(self, library_id: str, doc_id: str) -> Path:
        """获取 MinerU 块级结果路径。"""
        return self.get_parsed_dir(library_id, doc_id) / "mineru_blocks.json"

    def save_mineru_blocks(self, library_id: str, doc_id: str, blocks: List[Dict[str, Any]]) -> str:
        """保存 MinerU 块级结果。"""
        blocks_path = self.get_mineru_blocks_path(library_id, doc_id)
        with open(blocks_path, "w", encoding="utf-8") as f:
            json_blocks = blocks if isinstance(blocks, list) else []
            json.dump(json_blocks, f, ensure_ascii=False, indent=2)
        return str(blocks_path)

    def save_middle_json(self, library_id: str, doc_id: str, payload: Dict[str, Any]) -> str:
        """保存 middle.json 结构化中间数据。"""
        middle_path = self.get_middle_json_path(library_id, doc_id)
        data = payload if isinstance(payload, dict) else {}
        with open(middle_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(middle_path)

    def read_mineru_blocks(self, library_id: str, doc_id: str) -> List[Dict[str, Any]]:
        """读取 MinerU 块级结果。"""
        blocks_path = self.get_mineru_blocks_path(library_id, doc_id)
        if not blocks_path.exists():
            return []
        try:
            with open(blocks_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def read_markdown(self, library_id: str, doc_id: str) -> Optional[str]:
        """读取 Markdown 文件。"""
        edited_path = self.get_edited_markdown_path(library_id, doc_id)
        parsed_path = self.get_parsed_markdown_path(library_id, doc_id)
        target_path = edited_path if edited_path.exists() else parsed_path
        if target_path.exists():
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_latest_source_file(self, library_id: str, doc_id: str) -> Optional[str]:
        """获取源文件路径。"""
        source_dir = self.get_doc_root(library_id, doc_id) / "source"
        if source_dir.exists():
            files = sorted(
                [path for path in source_dir.iterdir() if path.is_file()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if files:
                return str(files[0])
        return None

    def ensure_doc_source_file(self, library_id: str, doc_id: str, file_path: Optional[str] = None) -> Optional[str]:
        """确保文档源文件存在于一文档一目录并返回规范路径。"""
        doc_source_dir = self.get_source_dir(library_id, doc_id)
        current_files = sorted([path for path in doc_source_dir.iterdir() if path.is_file()])
        if current_files:
            return str(current_files[0])
        source_candidate = Path(file_path) if file_path else None
        if source_candidate and source_candidate.exists() and source_candidate.is_file():
            target_path = doc_source_dir / source_candidate.name
            shutil.copy2(source_candidate, target_path)
            return str(target_path)
        return None

    def delete_document(self, library_id: str, doc_id: str) -> bool:
        """删除文档。"""
        doc_root = self._library_root(library_id) / "documents" / doc_id
        deleted = False
        if doc_root.exists():
            shutil.rmtree(doc_root)
            deleted = True
        return deleted

    def list_documents(self, library_id: str) -> List[dict]:
        """列出知识库中的文档。"""
        documents = []
        documents_dir = self._library_root(library_id) / "documents"
        if documents_dir.exists():
            for doc_root in documents_dir.iterdir():
                if not doc_root.is_dir():
                    continue
                source_dir = doc_root / "source"
                source_files = sorted([file for file in source_dir.glob("*") if file.is_file()])
                source_file = source_files[0] if source_files else None
                md_path = doc_root / "parsed" / "content.md"
                if source_file:
                    documents.append(
                        {
                            "id": doc_root.name,
                            "filename": source_file.name,
                            "source_path": str(source_file),
                            "has_markdown": md_path.exists(),
                            "created_at": datetime.fromtimestamp(source_file.stat().st_ctime).isoformat(),
                        }
                    )

        return documents

    def get_doc_root_path(self, library_id: str, doc_id: str) -> str:
        """获取文档根目录字符串路径。"""
        return str(self.get_doc_root(library_id, doc_id))

    def get_doc_manifest(self, library_id: str, doc_id: str) -> Dict[str, Any]:
        """获取文档清单。"""
        doc_root = self.get_doc_root(library_id, doc_id)
        source_file = self.get_latest_source_file(library_id, doc_id)
        parsed_path = self.get_parsed_markdown_path(library_id, doc_id)
        edited_path = self.get_edited_markdown_path(library_id, doc_id)
        assets_path = self.get_parsed_dir(library_id, doc_id) / "assets"
        raw_dir = self.get_parsed_dir(library_id, doc_id) / "raw"
        middle_json_path = self.get_middle_json_path(library_id, doc_id)
        mineru_blocks_path = self.get_mineru_blocks_path(library_id, doc_id)
        history_dir = self.get_edited_dir(library_id, doc_id) / "history"
        return {
            "doc_root": str(doc_root),
            "source_file": source_file,
            "parsed_markdown": str(parsed_path) if parsed_path.exists() else None,
            "edited_markdown": str(edited_path) if edited_path.exists() else None,
            "assets_dir": str(assets_path) if assets_path.exists() else None,
            "raw_dir": str(raw_dir) if raw_dir.exists() else None,
            "middle_json": str(middle_json_path) if middle_json_path.exists() else None,
            "mineru_blocks": str(mineru_blocks_path) if mineru_blocks_path.exists() else None,
            "history_files": sorted([str(path) for path in history_dir.glob("*.md")], reverse=True) if history_dir.exists() else [],
        }

    def reorganize_storage(self) -> None:
        self._reorganize_once()

    def _reorganize_once(self) -> None:
        for library_root in self.libraries_dir.glob("*"):
            if not library_root.is_dir():
                continue
            documents_dir = library_root / "documents"
            documents_dir.mkdir(parents=True, exist_ok=True)
            for doc_root in documents_dir.iterdir():
                if not doc_root.is_dir():
                    continue
                self._normalize_doc_layout(doc_root)

    def _normalize_doc_layout(self, doc_root: Path) -> None:
        for child in ("source", "parsed", "edited", "structured"):
            (doc_root / child).mkdir(parents=True, exist_ok=True)


file_storage = FileStorage()


# 延迟获取 AnGIneer LLM 客户端，避免循环导入。
def _get_llm_client():
    try:
        from angineer_core.infra.llm_client import llm_client
        return llm_client
    except ImportError:
        return None


# 保存 doc_blocks_graph.json 文件。
def _save_doc_blocks_graph(
    library_id: str,
    doc_id: str,
    result: A1StructureResult,
) -> str:
    graph_path = file_storage.get_graph_path(library_id, doc_id)

    payload = {
        "nodes": result.nodes,
        "edges": result.edges,
        "stats": result.stats,
        "generated_at": datetime.now().isoformat(),
    }

    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return str(graph_path)


# 把 canonical structure 投影为统一的 document_segments。
def _persist_structured_segments(
    library_id: str,
    doc_id: str,
    strategy: str,
    result: A1StructureResult,
) -> int:
    from docs_core.knowledge_service import knowledge_service

    structured_items = _build_a_structured_segment_items(result)
    return knowledge_service.save_document_segments(doc_id, library_id, strategy, structured_items)


# 归一化文本以提升图表相关块匹配稳定性。
def _normalize_related_text(text: str) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"[，。；：、“”‘’（）()\[\]【】<>《》,.;:!?！？·—\-~]", "", compact)
    return compact.strip().lower()


# 递归收集任意结构中的文本片段。
def _collect_texts_from_any(payload: Any) -> List[str]:
    fragments: List[str] = []

    def collect(node: Any) -> None:
        if isinstance(node, str):
            text = node.strip()
            if text:
                fragments.append(text)
            return
        if isinstance(node, list):
            for item in node:
                collect(item)
            return
        if isinstance(node, dict):
            for key in ("content", "text", "value"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value.strip())
            for value in node.values():
                if isinstance(value, (list, dict, str)):
                    collect(value)

    collect(payload)
    return list(dict.fromkeys(fragments))


# 把文本片段转换为可用于跨块匹配的归一化候选。
def _build_related_text_needles(values: List[str]) -> List[str]:
    needles: List[str] = []
    for value in values:
        normalized = _normalize_related_text(value)
        if normalized:
            needles.append(normalized)
    filtered = [value for value in needles if len(value) >= 2]
    filtered.sort(key=len, reverse=True)
    return list(dict.fromkeys(filtered))


# 判断文本是否看起来像图表题注编号。
def _is_caption_like_text(value: str) -> bool:
    return bool(re.match(r"^(图|表|figure|table)\s*[0-9a-z\u4e00-\u9fa5]", value, re.IGNORECASE))


# 判断候选行文本是否命中图表 caption 或 footnote 文本。
def _matches_related_text(row_text: str, needles: List[str]) -> bool:
    if not row_text or not needles:
        return False
    return any(
        needle in row_text
        or (len(row_text) >= 10 and row_text in needle)
        or (isinstance(row_text, str) and _is_caption_like_text(row_text) and needle.startswith(row_text[: min(len(row_text), 32)]))
        for needle in needles
    )


# 为图表块收集同页 caption 与 footnote 的关联 block_uid。
def _collect_media_related_block_refs(
    row: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    block_type = str(row.get("block_type") or "").strip().lower()
    if block_type not in {"image", "table"}:
        return {}

    content_json = row.get("content_json") if isinstance(row.get("content_json"), dict) else {}
    caption_key = "table_caption" if block_type == "table" else "image_caption"
    footnote_key = "table_footnote" if block_type == "table" else "image_footnote"
    caption_needles = _build_related_text_needles(_collect_texts_from_any(content_json.get(caption_key)))
    footnote_needles = _build_related_text_needles(_collect_texts_from_any(content_json.get(footnote_key)))
    if not caption_needles and not footnote_needles:
        return {}

    block_uid = str(row.get("block_uid") or "").strip()
    page_idx = int(row.get("page_idx", -1) or -1)
    excluded_types = {"image", "table", "header", "footer", "page_header", "page_number"}
    caption_refs: List[str] = []
    footnote_refs: List[str] = []

    for candidate in rows:
        candidate_uid = str(candidate.get("block_uid") or candidate.get("id") or "").strip()
        if not candidate_uid or candidate_uid == block_uid:
            continue
        candidate_page_idx = int(candidate.get("page_idx", -1) or -1)
        if candidate_page_idx != page_idx:
            continue
        candidate_type = str(candidate.get("block_type") or candidate.get("type") or "").strip().lower()
        if candidate_type in excluded_types:
            continue
        candidate_text = _normalize_related_text(str(candidate.get("plain_text") or candidate.get("text") or "").strip())
        if not candidate_text:
            continue
        if caption_needles and _matches_related_text(candidate_text, caption_needles):
            caption_refs.append(candidate_uid)
        if footnote_needles and _matches_related_text(candidate_text, footnote_needles):
            footnote_refs.append(candidate_uid)

    result: Dict[str, List[str]] = {}
    if caption_refs:
        result["caption_block_uids"] = list(dict.fromkeys(caption_refs))
    if footnote_refs:
        result["footnote_block_uids"] = list(dict.fromkeys(footnote_refs))
    return result


# 从 A1 结果构建 A_structured 片段投影。
def _build_a_structured_segment_items(
    result: A1StructureResult,
) -> List[Dict[str, Any]]:
    node_map: Dict[str, Dict[str, Any]] = {}
    for node in result.nodes:
        node_id = str(node.get("block_uid") or node.get("id") or "").strip()
        if node_id:
            node_map[node_id] = node

    derived_map: Dict[str, Dict[str, Any]] = {}
    for row in result.stats.get("derived_rows", []) or []:
        block_uid = str(row.get("block_uid") or "").strip()
        if block_uid:
            derived_map[block_uid] = row

    base_row_map: Dict[str, Dict[str, Any]] = {}
    base_rows: List[Dict[str, Any]] = result.stats.get("base_rows", []) or []
    for row in base_rows:
        block_uid = str(row.get("block_uid") or "").strip()
        if block_uid:
            base_row_map[block_uid] = row

    items: List[Dict[str, Any]] = []
    for order_index, row in enumerate(result.index_rows):
        block_uid = str(row.get("block_uid") or "").strip()
        if not block_uid:
            continue

        node = node_map.get(block_uid, {})
        derived_row = derived_map.get(block_uid, {})
        base_row = base_row_map.get(block_uid, {})
        block_type = str(row.get("block_type") or node.get("block_type") or "segment").strip() or "segment"
        page_idx = int(row.get("page_idx", node.get("page_idx", 0)) or 0)
        page_seq = int(derived_row.get("page_seq") or (page_idx + 1))
        block_seq = int(row.get("block_seq", node.get("block_seq", 0)) or 0)
        derived_level = row.get("derived_level")
        parent_block_uid = row.get("parent_uid") or derived_row.get("parent_block_uid")
        plain_text = str(row.get("plain_text") or node.get("plain_text") or "").strip()
        title_path = row.get("title_path") or derived_row.get("title_path")
        fallback_title = f"{block_type}@P{page_seq}B{block_seq}" if block_seq > 0 else f"{block_type}@P{page_seq}"
        title = plain_text or str(title_path or "").strip() or fallback_title
        parser_caption_refs = row.get("caption_block_uids") or node.get("caption_block_uids") or derived_row.get("caption_block_uids") or []
        parser_footnote_refs = row.get("footnote_block_uids") or node.get("footnote_block_uids") or derived_row.get("footnote_block_uids") or []
        caption_block_uids = [str(value).strip() for value in parser_caption_refs if str(value).strip()]
        footnote_block_uids = [str(value).strip() for value in parser_footnote_refs if str(value).strip()]
        caption_bboxes = row.get("caption_bboxes") or node.get("caption_bboxes") or derived_row.get("caption_bboxes")
        footnote_bboxes = row.get("footnote_bboxes") or node.get("footnote_bboxes") or derived_row.get("footnote_bboxes")
        if not caption_block_uids and not footnote_block_uids and base_row:
            related_refs = _collect_media_related_block_refs(base_row, base_rows)
            caption_block_uids = related_refs.get("caption_block_uids", [])
            footnote_block_uids = related_refs.get("footnote_block_uids", [])

        meta = {
            "source": "a_structured_index",
            "block_uid": block_uid,
            "node_id": block_uid,
            "block_id": block_uid,
            "source_block_id": block_uid,
            "block_uids": [block_uid],
            "node_ids": [block_uid],
            "item_type": block_type,
            "page_idx": page_idx,
            "page_seq": page_seq,
            "page": page_seq,
            "block_seq": block_seq,
            "derived_level": derived_level,
            "heading_level": derived_level,
            "level": derived_level,
            "title_path": title_path,
            "parent_uid": parent_block_uid,
            "parent_block_uid": parent_block_uid,
            "caption_block_uid": caption_block_uids[0] if len(caption_block_uids) == 1 else None,
            "caption_block_uids": caption_block_uids or None,
            "caption_bboxes": caption_bboxes,
            "footnote_block_uid": footnote_block_uids[0] if len(footnote_block_uids) == 1 else None,
            "footnote_block_uids": footnote_block_uids or None,
            "footnote_bboxes": footnote_bboxes,
            "bbox": node.get("bbox"),
            "bbox_source": node.get("bbox_source"),
            "derived_by": node.get("derived_by"),
            "confidence": node.get("confidence"),
        }
        meta = {key: value for key, value in meta.items() if value is not None}

        items.append(
            {
                "id": block_uid,
                "item_type": block_type,
                "title": title,
                "content": plain_text or title,
                "meta": meta,
                "order_index": order_index,
            }
        )

    return items


# 为文档构建结构化索引。
def build_structured_index_for_doc(
    library_id: str,
    doc_id: str,
    strategy: str = "A_structured",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    opts = options or {}
    use_llm = opts.get("use_llm", True)
    derive_version = opts.get("derive_version", "v1")

    parsed_dir = file_storage.get_parsed_dir(library_id, doc_id)
    raw_dir = file_storage.resolve_canonical_raw_dir(library_id, doc_id)

    content_list_path = raw_dir / "content_list_v2.json"
    if not content_list_path.exists():
        raise ValueError(f"文档尚无 MinerU 解析结果: {content_list_path}")

    llm_client = None
    if use_llm:
        llm_client = _get_llm_client()

    doc_name = ""
    doc_info = file_storage.get_doc_manifest(library_id, doc_id)
    if doc_info.get("source_file"):
        doc_name = Path(doc_info["source_file"]).name

    result = build_a1_from_mineru(
        parsed_dir=parsed_dir,
        doc_id=doc_id,
        doc_name=doc_name,
        llm_client=llm_client,
        options={
            "use_llm": use_llm,
            "derive_version": derive_version,
        },
    )

    if result.stats.get("error"):
        raise ValueError(f"构建结构失败: {result.stats.get('error')}")

    graph_path = _save_doc_blocks_graph(library_id, doc_id, result)
    doc_block_write_stats = persist_doc_blocks(result)
    structured_saved_count = _persist_structured_segments(library_id, doc_id, strategy, result)

    stats = {
        "nodes_count": len(result.nodes),
        "edges_count": len(result.edges),
        "index_rows_count": len(result.index_rows),
        "base_rows_count": doc_block_write_stats["inserted"],
        "derived_rows_count": doc_block_write_stats["updated"],
        "structured_items_saved_count": structured_saved_count,
        "llm_status": result.stats.get("llm_status", "disabled"),
        "derive_version": derive_version,
        "graph_path": graph_path,
    }

    return {
        "saved_count": structured_saved_count,
        "stats": stats,
    }


# 获取文档的块图谱。
def get_doc_blocks_graph(library_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    graph_path = file_storage.get_graph_path(library_id, doc_id)

    if not graph_path.exists():
        return None

    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)


# 从 Markdown 提取结构化项目。
def extract_structured_items_from_markdown(
    markdown_text: str,
    mineru_blocks: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    lines = markdown_text.splitlines()
    items: List[Dict[str, Any]] = []
    order_index = 0

    image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)')
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    clause_pattern = re.compile(r"^\s*(\d+(?:\.\d+)*(?:[、.)])?)\s+(.+)$")

    # 清理文本，保留中文字符、字母和数字，用于模糊匹配。
    def clean_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text).lower()

    # 判断当前行是否属于 Markdown 表格行。
    def is_table_row(text: str) -> bool:
        stripped = text.strip()
        return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2

    # 判断当前行是否为 Markdown 表格分隔行。
    def is_table_separator(text: str) -> bool:
        stripped = text.strip().replace(" ", "")
        return bool(stripped) and set(stripped) <= {"|", "-", ":"}

    blocks_by_type: Dict[str, List[Dict[str, Any]]] = {}
    if mineru_blocks:
        for block in mineru_blocks:
            block_type = block.get("type", "paragraph")
            block["cleaned_text"] = clean_text(block.get("text", ""))
            if block_type not in blocks_by_type:
                blocks_by_type[block_type] = []
            blocks_by_type[block_type].append(block)

    stats = {
        "total_items": 0,
        "matched_items": 0,
        "types": {},
    }
    last_matched_idx: Dict[str, int] = {}

    # 在指定类型块中查找最佳匹配项。
    def find_best_match(text: str, block_type: str) -> Optional[Dict[str, Any]]:
        if not mineru_blocks or block_type not in blocks_by_type:
            return None

        cleaned = clean_text(text)
        if not cleaned:
            return None

        blocks = blocks_by_type[block_type]
        start_idx = last_matched_idx.get(block_type, 0)
        best_match = None
        best_score = 0.0

        for idx in range(start_idx, len(blocks)):
            block = blocks[idx]
            block_text = block.get("cleaned_text", "")
            if not block_text:
                continue

            if cleaned == block_text:
                last_matched_idx[block_type] = idx + 1
                return block

            if cleaned in block_text or block_text in cleaned:
                shorter = min(len(cleaned), len(block_text))
                longer = max(len(cleaned), len(block_text))
                score = shorter / longer if longer else 0.0
                if score > best_score and score >= 0.6:
                    best_score = score
                    best_match = block

        if best_match:
            try:
                match_idx = blocks.index(best_match)
                last_matched_idx[block_type] = match_idx + 1
            except ValueError:
                pass

        return best_match

    # 把匹配到的 MinerU 元信息写入 meta。
    def enrich_meta(meta: Dict[str, Any], match: Optional[Dict[str, Any]], block_type: str) -> None:
        stats["total_items"] += 1
        stats["types"].setdefault(block_type, {"total": 0, "matched": 0})
        stats["types"][block_type]["total"] += 1

        if not match:
            return

        stats["matched_items"] += 1
        stats["types"][block_type]["matched"] += 1
        meta["mineru_match"] = {
            "bbox": match.get("bbox"),
            "page_idx": match.get("page_idx"),
            "block_idx": match.get("block_idx"),
            "type": match.get("type"),
        }

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        image_match = image_pattern.search(line)
        if image_match:
            alt_text = image_match.group(1) or ""
            src = image_match.group(2) or ""
            title = image_match.group(3) or alt_text or Path(src).name
            meta = {"line": idx + 1, "src": src}
            match = find_best_match(title, "image")
            enrich_meta(meta, match, "image")
            items.append(
                {
                    "item_type": "image",
                    "title": title,
                    "content": alt_text or title,
                    "meta": meta,
                    "order_index": order_index,
                }
            )
            order_index += 1
            idx += 1
            continue

        heading_match = heading_pattern.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            meta = {"line": idx + 1, "level": level}
            match = find_best_match(title, "title")
            enrich_meta(meta, match, "title")
            items.append(
                {
                    "item_type": "heading",
                    "title": title,
                    "content": title,
                    "meta": meta,
                    "order_index": order_index,
                }
            )
            order_index += 1
            idx += 1
            continue

        clause_match = clause_pattern.match(line)
        if clause_match:
            marker = clause_match.group(1).strip()
            content = clause_match.group(2).strip()
            title = f"{marker} {content}".strip()
            meta = {"line": idx + 1, "clause_marker": marker}
            match = find_best_match(title, "paragraph")
            enrich_meta(meta, match, "paragraph")
            items.append(
                {
                    "item_type": "clause",
                    "title": marker,
                    "content": content,
                    "meta": meta,
                    "order_index": order_index,
                }
            )
            order_index += 1
            idx += 1
            continue

        if is_table_row(line):
            table_lines = [line]
            next_idx = idx + 1
            while next_idx < len(lines) and is_table_row(lines[next_idx]):
                table_lines.append(lines[next_idx])
                next_idx += 1
            content = "\n".join(table_lines)
            title = table_lines[0].strip()
            meta = {"line": idx + 1, "rows": len(table_lines)}
            match = find_best_match(content, "table")
            enrich_meta(meta, match, "table")
            items.append(
                {
                    "item_type": "table",
                    "title": title[:50],
                    "content": content,
                    "meta": meta,
                    "order_index": order_index,
                }
            )
            order_index += 1
            idx = next_idx
            continue

        if is_table_separator(line):
            idx += 1
            continue

        text = line.strip()
        if text:
            meta = {"line": idx + 1}
            match = find_best_match(text, "segment")
            enrich_meta(meta, match, "segment")
            items.append(
                {
                    "item_type": "segment",
                    "title": text[:50],
                    "content": text,
                    "meta": meta,
                    "order_index": order_index,
                }
            )
            order_index += 1

        idx += 1

    total_items = stats["total_items"]
    matched_items = stats["matched_items"]
    match_rate = matched_items / total_items if total_items else 0
    print(f"[StructuredStrategy] Match rate: {match_rate:.2%} ({matched_items}/{total_items})")

    return items


__all__ = [
    "FileStorage",
    "_build_a_structured_segment_items",
    "build_structured_index_for_doc",
    "extract_structured_items_from_markdown",
    "file_storage",
    "get_doc_blocks_graph",
]
