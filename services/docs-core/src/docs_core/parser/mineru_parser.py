"""MinerU 文档解析服务"""
import json
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv
import requests
import time
import re

load_dotenv()


class MinerUParser:
    """MinerU 文档解析器"""

    def __init__(self):
        self.api_url = (os.getenv('MINERU_API_URL', 'https://mineru.net') or '').strip().rstrip('/')
        self.client_base_url = self._normalize_api_url(self.api_url)
        self.api_key = (
            os.getenv('MINERU_API_KEY', '')
            or os.getenv('MINERU_API_TOKEN', '')
        )
        self._client = None
        self._direct_base_url_checked = False
        self._direct_base_url: Optional[str] = None
        self.max_parse_retries = max(1, int(os.getenv('MINERU_PARSE_MAX_RETRIES', '4')))
        self.retry_delay_seconds = max(1, int(os.getenv('MINERU_PARSE_RETRY_DELAY_SECONDS', '2')))
        self.light_end_page = max(0, int(os.getenv('MINERU_LIGHT_END_PAGE', '10')))
        self.oom_retry_wait_seconds = max(1, int(os.getenv('MINERU_OOM_RETRY_WAIT_SECONDS', '8')))
        self.min_free_memory_mib = max(1, int(os.getenv('MINERU_MIN_FREE_MEMORY_MIB', '256')))

    def _normalize_api_url(self, api_url: str) -> str:
        """规范化 MinerU API 地址"""
        normalized = (api_url or '').strip().rstrip('/')
        if not normalized:
            return 'https://mineru.net/api/v4'
        if normalized.endswith('/api/v4'):
            return normalized
        if normalized.endswith('/api'):
            return f'{normalized}/v4'
        return f'{normalized}/api/v4'

    def _get_direct_base_candidates(self) -> List[str]:
        """获取 file_parse 直连地址候选列表"""
        candidates: List[str] = []
        raw = (self.api_url or '').strip().rstrip('/')
        if raw:
            candidates.append(raw)
            if raw.endswith('/file_parse'):
                candidates.append(raw[:-11].rstrip('/'))
            if raw.endswith('/api/v4'):
                candidates.append(raw[:-7].rstrip('/'))
            if raw.endswith('/api'):
                candidates.append(raw[:-4].rstrip('/'))
        normalized_client_base = (self.client_base_url or '').strip().rstrip('/')
        if normalized_client_base.endswith('/api/v4'):
            candidates.append(normalized_client_base[:-7].rstrip('/'))
        unique_candidates: List[str] = []
        for item in candidates:
            if item and item not in unique_candidates:
                unique_candidates.append(item)
        return unique_candidates

    def _detect_direct_base_url(self) -> Optional[str]:
        """检测是否支持 /file_parse 直连接口"""
        if self._direct_base_url_checked:
            return self._direct_base_url
        self._direct_base_url_checked = True
        for base_url in self._get_direct_base_candidates():
            try:
                response = requests.get(
                    f'{base_url}/openapi.json',
                    timeout=8,
                    verify=False
                )
                if response.status_code != 200:
                    continue
                payload = response.json()
                paths = payload.get('paths', {})
                if '/file_parse' in paths:
                    self._direct_base_url = base_url
                    return self._direct_base_url
            except Exception:
                continue
        return None

    def _extract_markdown_from_payload(self, payload: Any) -> Optional[str]:
        """从响应体中提取 Markdown 文本"""
        if isinstance(payload, str):
            text = payload.strip()
            return text if text else None
        if isinstance(payload, list):
            for item in payload:
                markdown = self._extract_markdown_from_payload(item)
                if markdown:
                    return markdown
            return None
        if isinstance(payload, dict):
            for key in ('markdown', 'md', 'md_content', 'content', 'text'):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            for value in payload.values():
                markdown = self._extract_markdown_from_payload(value)
                if markdown:
                    return markdown
        return None

    def _is_oom_message(self, text: str) -> bool:
        """判断是否为显存不足错误"""
        normalized = (text or '').lower()
        return 'cuda out of memory' in normalized or 'out of memory' in normalized or '显存' in normalized

    def _build_direct_retry_profiles(self) -> List[Dict[str, str]]:
        """构建直连接口重试配置"""
        return [
            {
                'return_md': 'true',
                'response_format_zip': 'false',
                'formula_enable': 'false',
                'table_enable': 'false',
                'parse_method': 'txt',
                'start_page_id': '0',
                'end_page_id': '0'
            },
            {
                'return_md': 'true',
                'response_format_zip': 'false',
                'formula_enable': 'false',
                'table_enable': 'false',
                'parse_method': 'txt',
                'start_page_id': '0',
                'end_page_id': str(self.light_end_page)
            },
            {
                'return_md': 'true',
                'response_format_zip': 'false',
                'formula_enable': 'false',
                'table_enable': 'false',
                'parse_method': 'auto',
                'start_page_id': '0',
                'end_page_id': str(self.light_end_page)
            },
            {
                'return_md': 'true',
                'response_format_zip': 'false',
                'formula_enable': 'true',
                'table_enable': 'true',
                'parse_method': 'auto'
            }
        ]

    def _extract_free_memory_mib(self, error_text: str) -> Optional[float]:
        """从错误文本中提取可用显存 MiB"""
        match = re.search(r'of which\s+([0-9.]+)\s+MiB\s+is free', error_text or '', flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _should_fast_fail_on_oom(self, error_text: str) -> bool:
        """根据可用显存判断是否应快速失败"""
        free_mib = self._extract_free_memory_mib(error_text)
        if free_mib is None:
            return False
        return free_mib < float(self.min_free_memory_mib)

    def _build_oom_hint(self, error_text: str) -> str:
        """构建显存不足提示信息"""
        match = re.search(r'of which\s+([0-9.]+\s+MiB)\s+is free', error_text or '', flags=re.IGNORECASE)
        free_text = match.group(1) if match else '当前可用显存不足'
        threshold_text = f'{self.min_free_memory_mib} MiB'
        return f'请先释放 GPU 任务后重试（检测到可用显存：{free_text}，建议至少保留：{threshold_text}）'

    def _parse_document_direct(self, input_path: str, output_dir: str) -> Optional[Dict[str, Any]]:
        """使用 /file_parse 接口直接解析文档"""
        base_url = self._detect_direct_base_url()
        if not base_url:
            return None
        try:
            retry_profiles = self._build_direct_retry_profiles()[:self.max_parse_retries]
            last_error = ''
            for index, data in enumerate(retry_profiles):
                with open(input_path, 'rb') as file_obj:
                    response = requests.post(
                        f'{base_url}/file_parse',
                        headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {},
                        data=data,
                        files=[('files', (Path(input_path).name, file_obj, 'application/pdf'))],
                        timeout=300,
                        verify=False
                    )
                detail = (response.text or '').strip()
                if response.status_code != 200:
                    detail = detail[:280] if detail else ''
                    last_error = f'Request failed with status {response.status_code}: {detail or "Unknown error"}'
                    if self._is_oom_message(last_error) and self._should_fast_fail_on_oom(last_error):
                        last_error = f'GPU 繁忙，检测到可用显存过低，已跳过重复重试：{last_error}；{self._build_oom_hint(last_error)}'
                        return {
                            'success': False,
                            'md_file': None,
                            'error': last_error
                        }
                    if self._is_oom_message(last_error) and index < len(retry_profiles) - 1:
                        time.sleep(self.oom_retry_wait_seconds)
                        continue
                    if self._is_oom_message(last_error):
                        last_error = f'显存不足，已执行{len(retry_profiles)}次降级重试后仍失败：{last_error}；{self._build_oom_hint(last_error)}'
                    return {
                        'success': False,
                        'md_file': None,
                        'error': last_error
                    }
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    payload = response.text or ''
                if isinstance(payload, dict) and payload.get('error'):
                    last_error = str(payload.get('error'))
                    if self._is_oom_message(last_error) and self._should_fast_fail_on_oom(last_error):
                        last_error = f'GPU 繁忙，检测到可用显存过低，已跳过重复重试：{last_error}；{self._build_oom_hint(last_error)}'
                        return {
                            'success': False,
                            'md_file': None,
                            'error': last_error
                        }
                    if self._is_oom_message(last_error) and index < len(retry_profiles) - 1:
                        time.sleep(self.oom_retry_wait_seconds)
                        continue
                    if self._is_oom_message(last_error):
                        last_error = f'显存不足，已执行{len(retry_profiles)}次降级重试后仍失败：{last_error}；{self._build_oom_hint(last_error)}'
                    return {
                        'success': False,
                        'md_file': None,
                        'error': last_error
                    }
                markdown = self._extract_markdown_from_payload(payload)
                if not markdown:
                    return {
                        'success': False,
                        'md_file': None,
                        'error': '解析成功但未返回 Markdown 内容'
                    }
                md_file_path = os.path.join(output_dir, 'parsed.md')
                with open(md_file_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(markdown)
                return {
                    'success': True,
                    'md_file': md_file_path,
                    'error': None
                }
            return {
                'success': False,
                'md_file': None,
                'error': f'显存不足，已执行{len(retry_profiles)}次降级重试后仍失败：{last_error}；{self._build_oom_hint(last_error)}'
            }
        except Exception as error:
            return {
                'success': False,
                'md_file': None,
                'error': f'解析请求失败: {error}'
            }

    def _get_client(self):
        """获取 MinerU 客户端"""
        if self._client is None:
            try:
                from mineru_rag import MinerUClient
                constructor_candidates = [
                    {'api_token': self.api_key},
                    {'api_key': self.api_key},
                    {'token': self.api_key},
                    {}
                ]
                last_error: Optional[Exception] = None
                for kwargs in constructor_candidates:
                    try:
                        self._client = MinerUClient(**kwargs)
                        break
                    except TypeError as error:
                        last_error = error
                if self._client is None:
                    if last_error:
                        raise last_error
                    raise RuntimeError('MinerUClient 初始化失败')
                for field in ('api_url', 'base_url', 'endpoint'):
                    if hasattr(self._client, field):
                        setattr(self._client, field, self.client_base_url)
                        break
            except ImportError:
                raise ImportError("请安装 mineru-rag: pip install mineru-rag[rag]")
        return self._client

    def parse_document(
        self,
        input_path: str,
        output_dir: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        解析文档

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录
            **kwargs: 其他参数

        Returns:
            解析结果字典
        """
        direct_result = self._parse_document_direct(input_path, output_dir)
        if direct_result is not None:
            return {
                'success': direct_result.get('success', False),
                'md_file': direct_result.get('md_file'),
                'error': direct_result.get('error'),
                'input_path': input_path,
                'output_dir': output_dir
            }

        client = self._get_client()

        result = client.process_file(
            input_path=input_path,
            output_path=output_dir,
            **kwargs
        )

        return {
            'success': result.get('success', False),
            'md_file': result.get('md_file'),
            'error': result.get('error'),
            'input_path': input_path,
            'output_dir': output_dir
        }

    def parse_documents_batch(
        self,
        file_paths: list,
        output_dir: str,
        **kwargs
    ) -> list:
        """
        批量解析文档

        Args:
            file_paths: 文件路径列表
            output_dir: 输出目录
            **kwargs: 其他参数

        Returns:
            解析结果列表
        """
        client = self._get_client()

        results = client.process_files_batch(
            file_paths=file_paths,
            output_dir=output_dir,
            **kwargs
        )

        return results


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
                from dotenv import load_dotenv
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


mineru_parser = MinerUParser()
mineru_rag = MinerURag()
