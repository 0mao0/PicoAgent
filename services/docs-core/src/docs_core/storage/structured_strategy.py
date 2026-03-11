import re
from typing import Any, Dict, List, Optional


def extract_structured_items_from_markdown(markdown_text: str, mineru_blocks: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
        # 移除所有非中文字符、字母和数字
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text).lower()

    # 预处理 mineru_blocks 以便匹配
    blocks_by_type: Dict[str, List[Dict[str, Any]]] = {}
    if mineru_blocks:
        for b in mineru_blocks:
            b_type = b.get('type', 'paragraph')
            # 提前注入清洗后的文本镜像
            b['cleaned_text'] = clean_text(b.get('text', ''))
            if b_type not in blocks_by_type:
                blocks_by_type[b_type] = []
            blocks_by_type[b_type].append(b)

    # 统计信息
    stats = {
        'total_items': 0,
        'matched_items': 0,
        'types': {}
    }

    # 用于优化搜索性能的游标
    last_matched_idx: Dict[str, int] = {}

    def find_best_match(item_text: str, item_type: str) -> Optional[Dict[str, Any]]:
        if not mineru_blocks:
            return None
        
        # 映射结构化类型到 mineru 类型
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
            
        # 使用清洗后的文本匹配逻辑
        item_text_clean = clean_text(item_text)
        if not item_text_clean:
            return None
            
        best_block = None
        max_overlap = 0
        
        # 性能优化：优先搜索上次匹配位置之后的区域 (Assuming roughly sequential order)
        start_search_idx = last_matched_idx.get(item_type, 0)
        
        # 生产环境优化：使用两轮搜索，第一轮找完全匹配/高重合，第二轮全局搜
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
                
                # 模糊匹配策略：完全包含、被包含、或者高比例重合
                if item_text_clean in b_text_clean or b_text_clean in item_text_clean:
                    overlap = min(len(item_text_clean), len(b_text_clean))
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_block = b
                        last_matched_idx[item_type] = i
                        # 如果是较长的文本且完全匹配，直接跳出提高性能
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
            # 标记匹配来源以便前端调试
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
            items.append(
                {
                    'item_type': 'heading',
                    'title': title,
                    'content': title,
                    'meta': meta,
                    'order_index': order_index
                }
            )
            order_index += 1

        clause_match = clause_pattern.match(line)
        if clause_match:
            title = clause_match.group(1).strip()
            content = clause_match.group(2).strip()
            meta = {'line': idx + 1}
            match = find_best_match(f"{title} {content}", 'clause')
            enrich_meta(meta, match, 'clause')
            items.append(
                {
                    'item_type': 'clause',
                    'title': title,
                    'content': content,
                    'meta': meta,
                    'order_index': order_index
                }
            )
            order_index += 1

        for image_match in image_pattern.finditer(line):
            title = image_match.group(1).strip() or '未命名图片'
            content = image_match.group(2).strip()
            meta = {'src': content, 'caption': (image_match.group(3) or '').strip(), 'line': idx + 1}
            match = find_best_match(title, 'image')
            enrich_meta(meta, match, 'image')
            items.append(
                {
                    'item_type': 'image',
                    'title': title,
                    'content': content,
                    'meta': meta,
                    'order_index': order_index
                }
            )
            order_index += 1

        if '|' in line:
            table_lines = []
            start_line = idx + 1
            cursor = idx
            while cursor < len(lines) and '|' in lines[cursor]:
                table_lines.append(lines[cursor])
                cursor += 1
            if len(table_lines) >= 2 and re.match(r'^\s*\|?\s*[-: ]+\|(?:\s*[-: ]+\|)*\s*$', table_lines[1]):
                table_text = '\n'.join(table_lines)
                header_line = table_lines[0].strip().strip('|')
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                meta = {'headers': headers, 'line': start_line, 'row_count': max(0, len(table_lines) - 2)}
                match = find_best_match(table_text[:100], 'table')
                enrich_meta(meta, match, 'table')
                items.append(
                    {
                        'item_type': 'table',
                        'title': f'表格@{start_line}',
                        'content': table_text,
                        'meta': meta,
                        'order_index': order_index
                    }
                )
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
                items.append(
                    {
                        'item_type': 'segment',
                        'title': f'段落@{paragraph_start}',
                        'content': content,
                        'meta': meta,
                        'order_index': order_index
                    }
                )
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
    
    # 打印匹配率统计
    if stats['total_items'] > 0:
        match_rate = stats['matched_items'] / stats['total_items'] * 100
        print(f"[StructuredStrategy] Match rate: {match_rate:.2f}% ({stats['matched_items']}/{stats['total_items']})")

    return items


def build_structured_index_for_doc(library_id: str, doc_id: str, strategy: str = 'A_structured') -> Dict[str, Any]:
    from docs_core import file_storage, knowledge_service
    markdown_content = file_storage.read_markdown(library_id, doc_id)
    if markdown_content is None:
        raise ValueError('文档尚无可用 Markdown 内容')
    
    # 尝试加载 mineru_blocks 以便注入坐标
    mineru_blocks = file_storage.read_mineru_blocks(library_id, doc_id)
    
    items = extract_structured_items_from_markdown(markdown_content, mineru_blocks=mineru_blocks)
    saved_count = knowledge_service.save_document_segments(doc_id, library_id, strategy, items)
    stats = knowledge_service.get_document_segment_stats(doc_id)
    return {'saved_count': saved_count, 'stats': stats}

