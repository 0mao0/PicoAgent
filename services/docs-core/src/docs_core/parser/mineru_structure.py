"""MinerU 结构化数据生成器 (A/B/C 融合算法)"""
import json
import re
from typing import Optional, Dict, Any, List, Set, Tuple

class MinerUStructureBuilder:
    """
    负责将 MinerU 的原始输出 (model.json, layout.json, content_list.json)
    转换为标准化的 mineru_blocks.json 结构。
    
    算法核心 (A/B/C 融合):
    - Source A (model.json): 提供核心文本、段落结构、基础 bbox。
    - Source B (layout.json): 提供页面尺寸、精细 bbox (图片/表格)。
    - Source C (content_list.json): 提供逻辑目录树 (Level Hierarchy)。
    """

    def __init__(self):
        self.highlight_excluded_types = {'page_header', 'header', 'page_number'}

    def build(
        self,
        model_data: Optional[Dict[str, Any]] = None,
        layout_data: Optional[Dict[str, Any]] = None,
        content_list_data: Optional[Dict[str, Any]] = None,
        other_json_data: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        主入口：构建标准化 blocks。
        如果提供了 model/layout/content_list，则使用 A/B/C 融合算法。
        否则 (兼容旧逻辑)，从 other_json_data 中提取并合并。
        """
        if model_data or layout_data:
            return self._build_from_abc(model_data, layout_data, content_list_data)
        
        # Fallback: legacy merge logic
        if other_json_data:
            raw_blocks = []
            for payload in other_json_data:
                # 假设 payload 带有 source_file 标记以便 _source_priority 工作
                source = payload.get('__source_file__', 'unknown.json')
                raw_blocks.extend(self._extract_blocks_from_payload(payload, source))
            return self._finalize_blocks(raw_blocks)
            
        return []

    def _build_from_abc(
        self,
        model_data: Optional[Dict[str, Any]],
        layout_data: Optional[Dict[str, Any]],
        content_list_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """A/B/C 融合算法实现"""
        
        # 1. 建立页面尺寸映射 (from Layout or Model)
        page_dimensions: Dict[int, Dict[str, float]] = {}
        
        # 尝试从 layout.json 获取页面尺寸
        if layout_data:
            # layout.json 可能是 {"pdf_info": [{"width": ..., "height": ...}, ...]} 
            # 或者 {"page_info": ...}
            # 或者是 list of pages
            pages = []
            if isinstance(layout_data, dict):
                if 'pdf_info' in layout_data:
                    pages = layout_data['pdf_info']
                elif 'page_info' in layout_data:
                    pages = layout_data['page_info']
            elif isinstance(layout_data, list):
                pages = layout_data

            for idx, page in enumerate(pages):
                # 有些格式可能是 page['width']，有些可能是 page['size'][0]
                w = self._read_first_numeric(page, ['width', 'w', 'page_width'])
                h = self._read_first_numeric(page, ['height', 'h', 'page_height'])
                
                # 如果没有直接宽高，尝试从 bbox 推断 (max x/y)
                if w is None or h is None:
                    # 尝试从该页 blocks 推断
                    blocks = page.get('para_blocks') or page.get('blocks') or []
                    max_x, max_y = 0.0, 0.0
                    for b in blocks:
                        bbox = self._normalize_bbox(b)
                        if bbox:
                            max_x = max(max_x, bbox[2])
                            max_y = max(max_y, bbox[3])
                    if max_x > 0 and max_y > 0:
                        w, h = max_x + 50, max_y + 50 # 加上边距估算
                
                if w and h:
                    page_dimensions[idx] = {'width': w, 'height': h}

        # 2. 提取 Source A (model.json) Blocks - 作为主干
        raw_blocks = []
        if model_data:
            # model.json 通常是 List[List[Block]] (按页)
            # 或者 Dict (包含 'model' key)
            pages_data = []
            if isinstance(model_data, list):
                pages_data = model_data
            elif isinstance(model_data, dict) and 'model' in model_data:
                pages_data = model_data['model']
            
            for page_idx, page_content in enumerate(pages_data):
                if isinstance(page_content, list):
                    # List of blocks
                    for block in page_content:
                        extracted = self._process_model_block(block, page_idx)
                        raw_blocks.extend(extracted)
                elif isinstance(page_content, dict):
                    # Page object
                    blocks = page_content.get('blocks', [])
                    for block in blocks:
                        extracted = self._process_model_block(block, page_idx)
                        raw_blocks.extend(extracted)

        # 3. 提取 Source C (content_list) 用于层级修正
        # 建立 block_id -> level 映射
        # content_list 通常包含 title/header 及其 level
        toc_map: Dict[str, int] = {} # text_hash -> level
        if content_list_data:
            toc_items = []
            if isinstance(content_list_data, list):
                toc_items = content_list_data
            elif isinstance(content_list_data, dict):
                # 可能是 {"content_list": [...]}
                toc_items = content_list_data.get('content_list', [])
            
            # 展平 TOC
            flat_toc = []
            # 如果是 List[List] (按页)
            if toc_items and isinstance(toc_items[0], list):
                 for page_items in toc_items:
                     flat_toc.extend(page_items)
            else:
                flat_toc = toc_items

            for item in flat_toc:
                # 尝试获取 level
                level = item.get('level') or item.get('text_level')
                if level is None and isinstance(item.get('content'), dict):
                    level = item['content'].get('level')
                
                text = self._resolve_block_text(item)
                if level is not None and text:
                     # 使用简单的文本哈希或前缀匹配
                     # 这里简化为 text 匹配
                     toc_map[text.strip()] = int(level)

        # 4. 融合与后处理
        # 应用 TOC level 到 raw_blocks
        for block in raw_blocks:
            text = block.get('text', '').strip()
            if text in toc_map:
                block['level'] = toc_map[text]
                block['type'] = 'title' # 强制修正为 title
            
            # 确保 page dimensions
            p_idx = block.get('page_idx', 0)
            if p_idx in page_dimensions:
                if 'page_width' not in block:
                    block['page_width'] = page_dimensions[p_idx]['width']
                if 'page_height' not in block:
                    block['page_height'] = page_dimensions[p_idx]['height']

        # 5. 构建父子关系 (Level Hierarchy)
        self._build_hierarchy(raw_blocks)

        return self._finalize_blocks(raw_blocks)

    def _assign_category_code(self, block: Dict[str, Any]) -> None:
        """根据 type 分配 0/X/T/F/E 类别标记"""
        btype = block.get('type', 'paragraph')
        
        # T (Title)
        if btype in ('title', 'header', 'page_header', 'section_header') or block.get('level') is not None:
            block['category_code'] = 'T'
            return
            
        # F (Figure/Table)
        if btype in ('table', 'figure', 'image', 'equation', 'formula', 'chart'):
            block['category_code'] = 'F'
            return
            
        # E (Element) - Default
        block['category_code'] = 'E'


    def _process_model_block(self, block_data: Dict[str, Any], page_idx: int) -> List[Dict[str, Any]]:
        """处理 model.json 中的单个 block，可能展开为多个 (如 list_items)"""
        results = []
        
        # 基础属性
        base_block = {
            'id': self._generate_id(),
            'page_idx': page_idx,
            'type': self._normalize_block_type(block_data.get('type')),
            'bbox': self._normalize_bbox(block_data),
            'text': '',
            'content': block_data.get('content') # 保留原始 content 用于调试
        }
        
        # 尝试提取文本
        # model.json 的 content 结构复杂
        content = block_data.get('content')
        
        # 1. 简单文本
        if isinstance(content, str):
            base_block['text'] = content
            results.append(base_block)
            return results

        # 2. 结构化 content
        if isinstance(content, dict):
            # 2.1 Title
            if 'title_content' in content:
                # 提取 title 文本
                fragments = []
                for item in content['title_content']:
                     if isinstance(item, dict) and 'content' in item:
                         fragments.append(item['content'])
                base_block['text'] = ' '.join(fragments)
                # 检查 level
                if 'level' in content:
                    base_block['level'] = content['level']
                results.append(base_block)
                return results

            # 2.2 Paragraph
            if 'paragraph_content' in content:
                fragments = []
                for item in content['paragraph_content']:
                     if isinstance(item, dict) and 'content' in item:
                         fragments.append(item['content'])
                base_block['text'] = ' '.join(fragments)
                results.append(base_block)
                return results

            # 2.3 List
            if 'list_items' in content:
                # 列表项通常是独立的 block，但这里是一个 block 包含多个 items
                # 我们可以创建一个父 block (list)，然后展开 items 为子 block (list_item)
                # 或者直接展开为多个平级的 block (简化处理)
                
                # 方案: 创建一个容器 block (list)
                list_block = base_block.copy()
                list_block['type'] = 'list'
                list_block['text'] = '' # 容器本身无文本
                results.append(list_block)
                
                for item in content['list_items']:
                    item_text = ''
                    if isinstance(item, str):
                        item_text = item
                    elif isinstance(item, dict):
                        # item 可能包含 item_content -> list of fragments
                        ic = item.get('item_content')
                        if isinstance(ic, list):
                            frags = [f.get('content', '') for f in ic if isinstance(f, dict)]
                            item_text = ' '.join(frags)
                        elif isinstance(ic, str):
                            item_text = ic
                    
                    if item_text:
                        item_block = {
                            'id': self._generate_id(),
                            'page_idx': page_idx,
                            'type': 'list_item',
                            'bbox': list_block['bbox'], # 暂时沿用父 bbox，虽然不准
                            'text': item_text,
                            'parent_id': list_block['id'] # 预先建立关系
                        }
                        results.append(item_block)
                return results

            # 2.4 Table (html)
            if 'html' in content:
                base_block['type'] = 'table'
                base_block['html'] = content['html']
                base_block['text'] = content.get('text', '') # 有些有纯文本摘要
                results.append(base_block)
                return results

        # Fallback: try standard resolution
        base_block['text'] = self._resolve_block_text(block_data)
        results.append(base_block)
        return results

    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def _build_hierarchy(self, blocks: List[Dict[str, Any]]) -> None:
        if not blocks:
            return

        pages: Dict[int, List[Dict[str, Any]]] = {}
        for block in blocks:
            page = block.get('page_idx', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(block)
            block['children'] = []
            # block['parent_id'] = None # already set or None

        for page_idx, page_blocks in pages.items():
            def get_area(b):
                bbox = b.get('bbox')
                if not bbox or len(bbox) < 4:
                    return 0
                return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

            sorted_blocks = sorted(page_blocks, key=get_area)

            for i, child in enumerate(sorted_blocks):
                child_bbox = child.get('bbox')
                if not child_bbox or len(child_bbox) < 4:
                    continue
                
                child_area = get_area(child)
                if child_area <= 0:
                    continue

                for parent in sorted_blocks[i+1:]:
                    parent_bbox = parent.get('bbox')
                    if not parent_bbox or len(parent_bbox) < 4:
                        continue
                    
                    is_contained = (
                        parent_bbox[0] <= child_bbox[0] + 0.01 and
                        parent_bbox[1] <= child_bbox[1] + 0.01 and
                        parent_bbox[2] >= child_bbox[2] - 0.01 and
                        parent_bbox[3] >= child_bbox[3] - 0.01
                    )
                    
                    if is_contained:
                        child['parent_id'] = parent['id']
                        if 'children' not in parent:
                            parent['children'] = []
                        parent['children'].append(child['id'])
                        break

    def _read_first_numeric(self, payload: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                try:
                    return float(stripped)
                except Exception:
                    continue
        return None

    def _resolve_block_text(self, payload: Dict[str, Any]) -> str:
        text_candidates: List[str] = []
        direct_text = payload.get('text')
        if isinstance(direct_text, str) and direct_text.strip():
            text_candidates.append(direct_text.strip())
        content = payload.get('content')
        if isinstance(content, str) and content.strip():
            text_candidates.append(content.strip())
        if isinstance(content, dict):
            for key in ('text', 'content', 'value'):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    text_candidates.append(value.strip())
            for list_key in ('title_content', 'paragraph_content', 'list_content'):
                value = content.get(list_key)
                if isinstance(value, list):
                    fragments = []
                    for item in value:
                        if isinstance(item, dict):
                            piece = item.get('content')
                            if isinstance(piece, str) and piece.strip():
                                fragments.append(piece.strip())
                    if fragments:
                        text_candidates.append(' '.join(fragments))
            
            list_items = content.get('list_items')
            if isinstance(list_items, list):
                list_fragments = []
                for item in list_items:
                    if not isinstance(item, dict):
                        continue
                    item_content = item.get('item_content')
                    if isinstance(item_content, str) and item_content.strip():
                        list_fragments.append(item_content.strip())
                    elif isinstance(item_content, list):
                        for sub in item_content:
                            if isinstance(sub, dict):
                                piece = sub.get('content')
                                if isinstance(piece, str) and piece.strip():
                                    list_fragments.append(piece.strip())
                if list_fragments:
                    text_candidates.append(' '.join(list_fragments))
        for key in ('text_content', 'title', 'heading'):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text_candidates.append(value.strip())
        return text_candidates[0] if text_candidates else ''

    def _normalize_block_type(self, raw_type: str) -> str:
        if not raw_type:
            return 'paragraph'
        normalized = raw_type.strip().lower()
        mapping = {
            'text': 'paragraph',
            'header': 'page_header',
            'interline_equation': 'equation_interline'
        }
        return mapping.get(normalized, normalized)

    def _source_priority(self, source_file: str) -> int:
        normalized = (source_file or '').lower()
        if normalized.endswith('_model.json') or '_model.json' in normalized:
            return 0
        if normalized.endswith('layout.json'):
            return 1
        if 'content_list_v2.json' in normalized:
            return 2
        if normalized.endswith('_content_list.json') or '_content_list.json' in normalized:
            return 3
        return 4

    def _normalize_bbox(self, payload: Dict[str, Any]) -> Optional[List[float]]:
        for key in ('bbox', 'rect', 'box', 'pdf_bbox', 'pdf_rect'):
            value = payload.get(key)
            if isinstance(value, (list, tuple)) and len(value) >= 4:
                coords: List[float] = []
                valid = True
                for item in value[:4]:
                    if isinstance(item, (int, float)):
                        coords.append(float(item))
                    elif isinstance(item, str):
                        stripped = item.strip()
                        if not stripped:
                            valid = False
                            break
                        try:
                            coords.append(float(stripped))
                        except Exception:
                            valid = False
                            break
                    else:
                        valid = False
                        break
                if valid:
                    return coords
        return None

    def _normalize_block_for_output(self, payload: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        raw_type = str(payload.get('type') or '').strip()
        normalized_type = self._normalize_block_type(raw_type)
        if not normalized_type or normalized_type in self.highlight_excluded_types:
            return None
        bbox = self._normalize_bbox(payload)
        if not bbox:
            return None
        page = self._read_first_numeric(payload, ['page', 'page_no', 'pageNo'])
        page_idx = self._read_first_numeric(payload, ['page_idx', 'page_index'])
        if page is None and page_idx is None:
            return None
        if page is None and page_idx is not None:
            page_idx_int = max(0, int(round(page_idx)))
            page_int = page_idx_int + 1
        elif page is not None and page_idx is None:
            page_int = max(1, int(round(page)))
            page_idx_int = page_int - 1
        else:
            page_int = max(1, int(round(page or 1)))
            page_idx_int = max(0, int(round(page_idx or 0)))
        block_id = payload.get('id')
        if not isinstance(block_id, str) or not block_id.strip():
            block_id = f'mineru-block-{index}'
        page_width = self._read_first_numeric(payload, ['page_width', 'pageWidth', 'width'])
        page_height = self._read_first_numeric(payload, ['page_height', 'pageHeight', 'height'])
        level = self._read_first_numeric(payload, ['level', 'text_level'])
        line_start = self._read_first_numeric(
            payload,
            ['line_start', 'lineStart', 'markdown_line_start', 'md_line_start', 'start_line', 'line']
        )
        line_end = self._read_first_numeric(
            payload,
            ['line_end', 'lineEnd', 'markdown_line_end', 'md_line_end', 'end_line']
        )
        text = self._resolve_block_text(payload)
        normalized_block: Dict[str, Any] = {
            'id': block_id.strip(),
            'type': normalized_type,
            'bbox': bbox,
            'page': page_int,
            'page_idx': page_idx_int,
            'source_file': payload.get('source_file') or ''
        }
        if text:
            normalized_block['text'] = text
        if isinstance(page_width, (int, float)) and page_width > 0:
            normalized_block['page_width'] = float(page_width)
        if isinstance(page_height, (int, float)) and page_height > 0:
            normalized_block['page_height'] = float(page_height)
        if isinstance(level, (int, float)):
            normalized_block['level'] = int(round(level))
        if isinstance(line_start, (int, float)):
            normalized_block['line_start'] = max(1, int(round(line_start)))
        if isinstance(line_end, (int, float)):
            normalized_block['line_end'] = max(1, int(round(line_end)))
        elif isinstance(line_start, (int, float)):
            normalized_block['line_end'] = max(1, int(round(line_start)))
        return normalized_block

    def _make_block_dedupe_key(self, payload: Dict[str, Any]) -> str:
        bbox = payload.get('bbox')
        bbox_key = ''
        if isinstance(bbox, list) and len(bbox) >= 4:
            rounded = [round(float(value), 4) for value in bbox[:4]]
            bbox_key = ','.join(str(item) for item in rounded)
        page = payload.get('page')
        page_idx = payload.get('page_idx')
        line_start = payload.get('line_start')
        line_end = payload.get('line_end')
        return f'{page}|{page_idx}|{bbox_key}|{line_start}|{line_end}'

    def _has_valid_bbox(self, payload: Dict[str, Any]) -> bool:
        return self._normalize_bbox(payload) is not None

    def _is_block_candidate(self, payload: Dict[str, Any]) -> bool:
        position_keys = ('bbox', 'rect', 'box', 'pdf_bbox', 'pdf_rect', 'position')
        page_keys = ('page', 'page_no', 'pageNo', 'page_index', 'page_idx')
        line_keys = ('line', 'line_start', 'line_end', 'lineStart', 'lineEnd', 'start_line', 'end_line')
        has_position = any(key in payload for key in position_keys)
        has_page = any(key in payload for key in page_keys)
        has_line = any(key in payload for key in line_keys)
        return has_position or (has_page and has_line)

    def _normalize_block(
        self,
        payload: Dict[str, Any],
        index: int,
        source: str,
        inherited: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        block = dict(payload)
        inherited_meta = inherited or {}
        position = block.get('position')
        if isinstance(position, dict):
            if 'bbox' not in block and isinstance(position.get('bbox'), list):
                block['bbox'] = position.get('bbox')
            if 'rect' not in block and isinstance(position.get('rect'), list):
                block['rect'] = position.get('rect')
            if 'page' not in block and isinstance(position.get('page'), (int, float)):
                block['page'] = position.get('page')
            if 'page' not in block and isinstance(position.get('page_no'), (int, float)):
                block['page'] = position.get('page_no')
            if 'page' not in block and isinstance(position.get('pageNo'), (int, float)):
                block['page'] = position.get('pageNo')
            if 'page_idx' not in block and isinstance(position.get('page_idx'), (int, float)):
                block['page_idx'] = position.get('page_idx')
            if 'page_idx' not in block and isinstance(position.get('page_index'), (int, float)):
                block['page_idx'] = position.get('page_index')
        if 'page' not in block and isinstance(block.get('page_no'), (int, float)):
            block['page'] = block.get('page_no')
        if 'page' not in block and isinstance(block.get('pageNo'), (int, float)):
            block['page'] = block.get('pageNo')
        if 'page_idx' not in block and isinstance(block.get('page_index'), (int, float)):
            block['page_idx'] = block.get('page_index')
        if 'page' not in block and isinstance(inherited_meta.get('page'), (int, float)):
            block['page'] = inherited_meta.get('page')
        if 'page_idx' not in block and isinstance(inherited_meta.get('page_idx'), (int, float)):
            block['page_idx'] = inherited_meta.get('page_idx')
        if 'page_width' not in block and isinstance(inherited_meta.get('page_width'), (int, float)):
            block['page_width'] = inherited_meta.get('page_width')
        if 'page_height' not in block and isinstance(inherited_meta.get('page_height'), (int, float)):
            block['page_height'] = inherited_meta.get('page_height')
        if 'page' not in block and isinstance(block.get('page_idx'), (int, float)):
            block['page'] = int(block['page_idx']) + 1
        if 'page_idx' not in block and isinstance(block.get('page'), (int, float)):
            block['page_idx'] = max(0, int(block['page']) - 1)
        content = block.get('content')
        if isinstance(content, dict) and isinstance(content.get('level'), (int, float)) and 'level' not in block:
            block['level'] = int(content.get('level'))
        if isinstance(block.get('text_level'), (int, float)) and 'level' not in block:
            block['level'] = int(block.get('text_level'))
        if not block.get('id'):
            block['id'] = f'mineru-block-{index}'
        block['source_file'] = source
        return block

    def _extract_blocks_from_payload(self, payload: Any, source: str) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []

        def walk(value: Any, inherited: Dict[str, Any]) -> None:
            if isinstance(value, dict):
                next_inherited = dict(inherited)
                if isinstance(value.get('page'), (int, float)):
                    next_inherited['page'] = value.get('page')
                    next_inherited['page_idx'] = max(0, int(value.get('page')) - 1)
                if isinstance(value.get('page_no'), (int, float)):
                    next_inherited['page'] = value.get('page_no')
                    next_inherited['page_idx'] = max(0, int(value.get('page_no')) - 1)
                if isinstance(value.get('pageNo'), (int, float)):
                    next_inherited['page'] = value.get('pageNo')
                    next_inherited['page_idx'] = max(0, int(value.get('pageNo')) - 1)
                if isinstance(value.get('page_idx'), (int, float)):
                    page_idx = int(value.get('page_idx'))
                    next_inherited['page_idx'] = page_idx
                    next_inherited['page'] = page_idx + 1
                if isinstance(value.get('page_index'), (int, float)):
                    page_idx = int(value.get('page_index'))
                    next_inherited['page_idx'] = page_idx
                    next_inherited['page'] = page_idx + 1
                page_size = value.get('page_size')
                if isinstance(page_size, (list, tuple)) and len(page_size) >= 2:
                    if isinstance(page_size[0], (int, float)):
                        next_inherited['page_width'] = float(page_size[0])
                    if isinstance(page_size[1], (int, float)):
                        next_inherited['page_height'] = float(page_size[1])
                if self._is_block_candidate(value):
                    result.append(self._normalize_block(value, len(result), source, next_inherited))
                for child in value.values():
                    walk(child, next_inherited)
                return
            if isinstance(value, list):
                if value and all(isinstance(child, list) for child in value):
                    for page_idx, child in enumerate(value):
                        page_inherited = dict(inherited)
                        if not isinstance(page_inherited.get('page_idx'), (int, float)):
                            page_inherited['page_idx'] = page_idx
                            page_inherited['page'] = page_idx + 1
                        walk(child, page_inherited)
                    return
                for child in value:
                    walk(child, inherited)

        walk(payload, {})
        for index, block in enumerate(result):
            if not isinstance(block.get('id'), str) or not block.get('id'):
                block['id'] = f'mineru-block-{index}'
        return result

    def _finalize_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(blocks, list) or not blocks:
            return []
        merged: Dict[str, Dict[str, Any]] = {}
        priorities: Dict[str, int] = {}
        normalized_candidates: List[Dict[str, Any]] = []
        page_dimensions: Dict[int, Dict[str, float]] = {}
        
        for index, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            
            sub_blocks = []
            content = block.get('content')
            if isinstance(content, dict):
                list_items = content.get('list_items')
                if isinstance(list_items, list) and len(list_items) > 0:
                    if any(self._has_valid_bbox(item) for item in list_items if isinstance(item, dict)):
                        parent_id = block.get('id') or f'mineru-block-{index}'
                        for sub_idx, item in enumerate(list_items):
                            if not isinstance(item, dict):
                                continue
                            if not self._has_valid_bbox(item):
                                continue
                            sub_block = item.copy()
                            for key in ['page', 'page_idx', 'page_width', 'page_height', 'source_file']:
                                if key in block and key not in sub_block:
                                    sub_block[key] = block[key]
                            if 'type' not in sub_block:
                                sub_block['type'] = 'list_item'
                            sub_block['id'] = f"{parent_id}-item-{sub_idx}"
                            if 'text' not in sub_block and 'content' not in sub_block:
                                item_content = item.get('item_content')
                                if item_content:
                                    sub_block['text'] = item_content
                            sub_blocks.append(sub_block)

            if sub_blocks:
                for sub in sub_blocks:
                    normalized = self._normalize_block_for_output(sub, index)
                    if normalized:
                        normalized_candidates.append(normalized)
            else:
                normalized = self._normalize_block_for_output(block, index)
                if normalized:
                    normalized_candidates.append(normalized)

        for normalized in normalized_candidates:
            page_idx = int(normalized.get('page_idx') or 0)
            width = normalized.get('page_width')
            height = normalized.get('page_height')
            if isinstance(width, (int, float)) and isinstance(height, (int, float)):
                current = page_dimensions.get(page_idx, {'width': 0.0, 'height': 0.0})
                page_dimensions[page_idx] = {
                    'width': max(float(current.get('width') or 0.0), float(width)),
                    'height': max(float(current.get('height') or 0.0), float(height))
                }
            
            dedupe_key = self._make_block_dedupe_key(normalized)
            source_priority = self._source_priority(str(normalized.get('source_file') or ''))
            current_priority = priorities.get(dedupe_key)
            if current_priority is None or source_priority < current_priority:
                merged[dedupe_key] = normalized
                priorities[dedupe_key] = source_priority

        has_primary_content = any(
            self._source_priority(str(item.get('source_file') or '')) <= 1 for item in normalized_candidates
        )
        finalized = [
            item for item in merged.values()
            if (not has_primary_content) 
            or self._source_priority(str(item.get('source_file') or '')) <= 1
            or item.get('type') in ('list', 'table', 'toc', 'image', 'formula')
        ]
        for item in finalized:
            page_idx = int(item.get('page_idx') or 0)
            page_dim = page_dimensions.get(page_idx) or {}
            if 'page_width' not in item and isinstance(page_dim.get('width'), (int, float)) and page_dim.get('width', 0) > 0:
                item['page_width'] = float(page_dim.get('width'))
            if 'page_height' not in item and isinstance(page_dim.get('height'), (int, float)) and page_dim.get('height', 0) > 0:
                item['page_height'] = float(page_dim.get('height'))
        finalized.sort(key=lambda item: (
            int(item.get('page_idx') or 0),
            float(item.get('bbox', [0, 0, 0, 0])[1]),
            float(item.get('bbox', [0, 0, 0, 0])[0]),
            str(item.get('id') or '')
        ))
        for index, item in enumerate(finalized):
            item['id'] = f'mineru-block-{index}'
        
        self._build_hierarchy(finalized)
        
        # 6. 分配 0/X/T/F/E 类别标记
        for block in finalized:
            self._assign_category_code(block)
        
        return finalized

    def _build_hierarchy(self, blocks: List[Dict[str, Any]]) -> None:
        if not blocks:
            return

        pages: Dict[int, List[Dict[str, Any]]] = {}
        for block in blocks:
            page = block.get('page_idx', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(block)
            block['children'] = []
            block['parent_id'] = None

        for page_idx, page_blocks in pages.items():
            def get_area(b):
                bbox = b.get('bbox')
                if not bbox or len(bbox) < 4:
                    return 0
                return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

            sorted_blocks = sorted(page_blocks, key=get_area)

            for i, child in enumerate(sorted_blocks):
                child_bbox = child.get('bbox')
                if not child_bbox or len(child_bbox) < 4:
                    continue
                
                child_area = get_area(child)
                if child_area <= 0:
                    continue

                for parent in sorted_blocks[i+1:]:
                    parent_bbox = parent.get('bbox')
                    if not parent_bbox or len(parent_bbox) < 4:
                        continue
                    
                    is_contained = (
                        parent_bbox[0] <= child_bbox[0] + 0.01 and
                        parent_bbox[1] <= child_bbox[1] + 0.01 and
                        parent_bbox[2] >= child_bbox[2] - 0.01 and
                        parent_bbox[3] >= child_bbox[3] - 0.01
                    )
                    
                    if is_contained:
                        child['parent_id'] = parent['id']
                        if 'children' not in parent:
                            parent['children'] = []
                        parent['children'].append(child['id'])
                        break
