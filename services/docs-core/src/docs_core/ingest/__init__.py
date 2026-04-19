"""docs_core 文档吸收主链导出。"""

from .canonical import (
    BoundingBox,
    CanonicalBlock,
    CanonicalChunk,
    CanonicalDocument,
    CanonicalOutlineNode,
    CanonicalPage,
    CanonicalTable,
    CitationTarget,
    build_canonical_blocks,
    build_canonical_chunks,
    build_canonical_document,
    build_canonical_outlines,
    build_canonical_tables,
)
from .parser import MinerUParser, mineru_parser
from .storage import FileStorage, build_structured_index_for_doc, file_storage, get_doc_blocks_graph
from .structured import (
    RawFilesStructureBuilder,
    StructuredResult,
    build_graph_from_rawfiles,
    build_structured_from_rawfiles,
    build_table_representations,
    classify_table,
    extract_table_features,
)

__all__ = [
    "BoundingBox",
    "CanonicalBlock",
    "CanonicalChunk",
    "CanonicalDocument",
    "CanonicalOutlineNode",
    "CanonicalPage",
    "CanonicalTable",
    "CitationTarget",
    "FileStorage",
    "MinerUParser",
    "RawFilesStructureBuilder",
    "StructuredResult",
    "build_canonical_blocks",
    "build_canonical_chunks",
    "build_canonical_document",
    "build_canonical_outlines",
    "build_canonical_tables",
    "build_graph_from_rawfiles",
    "build_structured_from_rawfiles",
    "build_structured_index_for_doc",
    "build_table_representations",
    "classify_table",
    "extract_table_features",
    "file_storage",
    "get_doc_blocks_graph",
    "mineru_parser",
]
