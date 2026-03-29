"""
结构主链持久化 - A1 结构结果生成与持久化

职责：
- 调用 mineru_structure.build_graph_from_mineru 得到 A1
- 落盘 parsed/doc_blocks_graph.json
- 写入 data/knowledge_base/knowledge_index.sqlite
- 负责幂等与事务，不写算法细节
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from docs_core.storage.file_storage import file_storage
from docs_core.storage.knowledge_store import KnowledgeIndexStore
from docs_core.parser.mineru_structure import (
    build_graph_from_mineru,
    A1StructureResult
)


_index_store = KnowledgeIndexStore()


def _get_llm_client():
    """延迟获取 AnGIneer LLM 客户端，避免循环导入。"""
    try:
        from angineer_core.infra.llm_client import llm_client
        return llm_client
    except ImportError:
        return None


# 持久化 doc_blocks 主索引。
def _persist_doc_blocks(result: A1StructureResult) -> Dict[str, int]:
    base_rows = result.stats.get("base_rows", []) or []
    derived_rows = result.stats.get("derived_rows", []) or []
    doc_id = ""
    if base_rows:
        doc_id = str(base_rows[0].get("doc_id") or "")
    elif derived_rows:
        doc_id = str(derived_rows[0].get("doc_id") or "")
    if doc_id:
        _index_store.clear_doc_blocks(doc_id)
    inserted = _index_store.insert_doc_blocks_base_rows(base_rows) if base_rows else 0
    updated = _index_store.update_doc_blocks_derived_rows(derived_rows) if derived_rows else 0
    return {"inserted": inserted, "updated": updated}


def _save_doc_blocks_graph(
    library_id: str,
    doc_id: str,
    result: A1StructureResult
) -> str:
    """保存 doc_blocks_graph.json 文件。"""
    graph_path = file_storage.get_graph_path(library_id, doc_id)
    
    payload = {
        "nodes": result.nodes,
        "edges": result.edges,
        "stats": result.stats,
        "generated_at": datetime.now().isoformat()
    }
    
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    return str(graph_path)


# 把 canonical structure 投影为统一的 document_segments。
def _persist_structured_segments(
    library_id: str,
    doc_id: str,
    strategy: str,
    result: A1StructureResult,
) -> int:
    from docs_core.api.knowledge_api import knowledge_service

    structured_items = _build_a_structured_segment_items(result)
    return knowledge_service.save_document_segments(doc_id, library_id, strategy, structured_items)


def _normalize_related_text(text: str) -> str:
    """归一化文本以提升图表相关块匹配稳定性。"""
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"[，。；：、“”‘’（）()\[\]【】<>《》,.;:!?！？·—\-~]", "", compact)
    return compact.strip().lower()


def _collect_texts_from_any(payload: Any) -> List[str]:
    """递归收集任意结构中的文本片段。"""
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


def _build_related_text_needles(values: List[str]) -> List[str]:
    """把文本片段转换为可用于跨块匹配的归一化候选。"""
    needles: List[str] = []
    for value in values:
        normalized = _normalize_related_text(value)
        if normalized:
            needles.append(normalized)
    filtered = [value for value in needles if len(value) >= 2]
    filtered.sort(key=len, reverse=True)
    return list(dict.fromkeys(filtered))


def _is_caption_like_text(value: str) -> bool:
    """判断文本是否看起来像图表题注编号。"""
    return bool(re.match(r"^(图|表|figure|table)\s*[0-9a-z\u4e00-\u9fa5]", value, re.IGNORECASE))


def _matches_related_text(row_text: str, needles: List[str]) -> bool:
    """判断候选行文本是否命中图表 caption 或 footnote 文本。"""
    if not row_text or not needles:
        return False
    return any(
        needle in row_text
        or (len(row_text) >= 10 and row_text in needle)
        or (_is_caption_like_text(row_text) and needle.startswith(row_text[: min(len(row_text), 32)]))
        for needle in needles
    )


def _collect_media_related_block_refs(
    row: Dict[str, Any],
    base_rows: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """为图表块收集同页 caption 与 footnote 的关联 block_uid。"""
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

    for candidate in base_rows:
        candidate_uid = str(candidate.get("block_uid") or candidate.get("id") or "").strip()
        if not candidate_uid or candidate_uid == block_uid:
            continue
        candidate_page_idx = int(candidate.get("page_idx", -1) or -1)
        if candidate_page_idx != page_idx:
            continue
        candidate_type = str(candidate.get("block_type") or candidate.get("type") or "").strip().lower()
        if candidate_type in excluded_types:
            continue
        candidate_text_raw = str(candidate.get("plain_text") or candidate.get("text") or "").strip()
        candidate_text = _normalize_related_text(candidate_text_raw)
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


def _build_a_structured_segment_items(
    result: A1StructureResult
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
            "confidence": node.get("confidence")
        }
        meta = {key: value for key, value in meta.items() if value is not None}

        items.append({
            "id": block_uid,
            "item_type": block_type,
            "title": title,
            "content": plain_text or title,
            "meta": meta,
            "order_index": order_index
        })

    return items


def build_structured_index_for_doc(
    library_id: str,
    doc_id: str,
    strategy: str = 'A_structured',
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    为文档构建结构化索引。
    
    Args:
        library_id: 知识库ID
        doc_id: 文档ID
        strategy: 策略名称 (默认 A_structured)
        options: 可选配置项
            - use_llm: 是否使用 LLM 细化标题层级 (默认 True)
            - derive_version: 推导版本标识
    
    Returns:
        包含 saved_count 和 stats 的字典
    """
    opts = options or {}
    use_llm = opts.get("use_llm", True)
    derive_version = opts.get("derive_version", "v1")
    
    parsed_dir = file_storage.get_parsed_dir(library_id, doc_id)
    raw_dir = file_storage.resolve_canonical_raw_dir(library_id, doc_id)

    content_list_path = raw_dir / 'content_list_v2.json'
    if not content_list_path.exists():
        raise ValueError(f'文档尚无 MinerU 解析结果: {content_list_path}')
    
    llm_client = None
    if use_llm:
        llm_client = _get_llm_client()
    
    doc_name = ""
    doc_info = file_storage.get_doc_manifest(library_id, doc_id)
    if doc_info.get("source_file"):
        doc_name = Path(doc_info["source_file"]).name
    
    result = build_graph_from_mineru(
        parsed_dir=parsed_dir,
        doc_id=doc_id,
        doc_name=doc_name,
        llm_client=llm_client,
        options={
            "use_llm": use_llm,
            "derive_version": derive_version
        }
    )
    
    if result.stats.get("error"):
        raise ValueError(f'构建结构失败: {result.stats.get("error")}')
    
    graph_path = _save_doc_blocks_graph(library_id, doc_id, result)
    doc_block_write_stats = _persist_doc_blocks(result)
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
        "graph_path": graph_path
    }
    
    return {
        "saved_count": structured_saved_count,
        "stats": stats
    }


def get_doc_blocks_graph(library_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """获取文档的块图谱。"""
    graph_path = file_storage.get_graph_path(library_id, doc_id)
    
    if not graph_path.exists():
        return None
    
    with open(graph_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def query_doc_blocks(
    doc_id: str,
    block_type: Optional[str] = None,
    derived_level: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """查询文档块记录。"""
    return _index_store.query_doc_blocks(
        doc_id=doc_id,
        block_type=block_type,
        derived_level=derived_level,
        limit=limit,
    )


def get_doc_blocks_stats(doc_id: str) -> Dict[str, Any]:
    """获取文档块统计信息。"""
    return _index_store.get_doc_blocks_stats(doc_id)


def extract_structured_items_from_markdown(
    markdown_text: str,
    mineru_blocks: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """从 Markdown 提取结构化项目（兼容旧接口）。"""
    import re
    
    lines = markdown_text.splitlines()
    items: List[Dict[str, Any]] = []
    order_index = 0

    image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)')
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
    clause_pattern = re.compile(r'^\s*(\d+(?:\.\d+)*(?:[、.)])?)\s+(.+)$')

    def clean_text(text: str) -> str:
        """清理文本，保留中文字符、字母和数字，用于模糊匹配"""
        if not text:
            return ""
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text).lower()

    blocks_by_type: Dict[str, List[Dict[str, Any]]] = {}
    if mineru_blocks:
        for b in mineru_blocks:
            b_type = b.get('type', 'paragraph')
            b['cleaned_text'] = clean_text(b.get('text', ''))
            if b_type not in blocks_by_type:
                blocks_by_type[b_type] = []
            blocks_by_type[b_type].append(b)

    stats = {
        'total_items': 0,
        'matched_items': 0,
        'types': {}
    }

    last_matched_idx: Dict[str, int] = {}

    def find_best_match(item_text: str, item_type: str) -> Optional[Dict[str, Any]]:
        if not mineru_blocks:
            return None
        
        type_map = {
            'heading': ['title', 'heading'],
            'clause': ['title', 'paragraph', 'list'],
            'segment': ['paragraph', 'list', 'text'],
            'image': ['image'],
            'table': ['table']
        }
        target_types = type_map.get(item_type, ['paragraph'])
        
        candidates = []
        for t in target_types:
            candidates.extend(blocks_by_type.get(t, []))
            
        if not candidates:
            return None
            
        item_text_clean = clean_text(item_text)
        if not item_text_clean:
            return None
            
        best_block = None
        max_overlap = 0
        
        start_search_idx = last_matched_idx.get(item_type, 0)
        
        search_ranges = [
            range(start_search_idx, len(candidates)),
            range(0, start_search_idx)
        ]
        
        for r in search_ranges:
            for i in r:
                b = candidates[i]
                b_text_clean = b.get('cleaned_text', '')
                if not b_text_clean:
                    continue
                
                if item_text_clean in b_text_clean or b_text_clean in item_text_clean:
                    overlap = min(len(item_text_clean), len(b_text_clean))
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_block = b
                        last_matched_idx[item_type] = i
                        if overlap > 50:
                            break
            if best_block:
                break
                    
        return best_block

    def enrich_meta(meta: Dict[str, Any], block: Optional[Dict[str, Any]], item_type: str):
        stats['total_items'] += 1
        stats['types'][item_type] = stats['types'].get(item_type, 0) + 1
        if block:
            stats['matched_items'] += 1
            meta['bbox'] = block.get('bbox')
            meta['page'] = block.get('page')
            meta['page_idx'] = block.get('page_idx')
            if 'page_width' in block:
                meta['page_width'] = block['page_width']
            if 'page_height' in block:
                meta['page_height'] = block['page_height']
            meta['mineru_block_id'] = block.get('id')
            meta['match_source'] = 'backend_stitching'

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        heading_match = heading_pattern.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            meta = {'level': level, 'line': idx + 1}
            match = find_best_match(title, 'heading')
            enrich_meta(meta, match, 'heading')
            items.append({
                'item_type': 'heading',
                'title': title,
                'content': title,
                'meta': meta,
                'order_index': order_index
            })
            order_index += 1

        clause_match = clause_pattern.match(line)
        if clause_match:
            title = clause_match.group(1).strip()
            content = clause_match.group(2).strip()
            meta = {'line': idx + 1}
            match = find_best_match(f"{title} {content}", 'clause')
            enrich_meta(meta, match, 'clause')
            items.append({
                'item_type': 'clause',
                'title': title,
                'content': content,
                'meta': meta,
                'order_index': order_index
            })
            order_index += 1

        for image_match in image_pattern.finditer(line):
            title = image_match.group(1).strip() or '未命名图片'
            content = image_match.group(2).strip()
            meta = {
                'src': content,
                'caption': (image_match.group(3) or '').strip(),
                'line': idx + 1
            }
            match = find_best_match(title, 'image')
            enrich_meta(meta, match, 'image')
            items.append({
                'item_type': 'image',
                'title': title,
                'content': content,
                'meta': meta,
                'order_index': order_index
            })
            order_index += 1

        if '|' in line:
            table_lines = []
            start_line = idx + 1
            cursor = idx
            while cursor < len(lines) and '|' in lines[cursor]:
                table_lines.append(lines[cursor])
                cursor += 1
            if len(table_lines) >= 2 and re.match(
                r'^\s*\|?\s*[-: ]+\|(?:\s*[-: ]+\|)*\s*$',
                table_lines[1]
            ):
                table_text = '\n'.join(table_lines)
                header_line = table_lines[0].strip().strip('|')
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                meta = {
                    'headers': headers,
                    'line': start_line,
                    'row_count': max(0, len(table_lines) - 2)
                }
                match = find_best_match(table_text[:100], 'table')
                enrich_meta(meta, match, 'table')
                items.append({
                    'item_type': 'table',
                    'title': f'表格@{start_line}',
                    'content': table_text,
                    'meta': meta,
                    'order_index': order_index
                })
                order_index += 1
                idx = cursor - 1

        idx += 1

    paragraph_buffer: List[str] = []
    paragraph_start = 1
    
    def add_paragraph_item():
        nonlocal order_index
        if paragraph_buffer:
            content = '\n'.join(paragraph_buffer).strip()
            if content and len(content) >= 20:
                meta = {'line': paragraph_start}
                match = find_best_match(content, 'segment')
                enrich_meta(meta, match, 'segment')
                items.append({
                    'item_type': 'segment',
                    'title': f'段落@{paragraph_start}',
                    'content': content,
                    'meta': meta,
                    'order_index': order_index
                })
                order_index += 1

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            add_paragraph_item()
            paragraph_buffer = []
            continue
        if line.strip().startswith('#') or line.strip().startswith('|') or line.strip().startswith('!['):
            add_paragraph_item()
            paragraph_buffer = []
            continue
        if not paragraph_buffer:
            paragraph_start = line_no
        paragraph_buffer.append(line)

    add_paragraph_item()
    
    if stats['total_items'] > 0:
        match_rate = stats['matched_items'] / stats['total_items'] * 100
        print(f"[StructuredStrategy] Match rate: {match_rate:.2f}% ({stats['matched_items']}/{stats['total_items']})")

    return items
