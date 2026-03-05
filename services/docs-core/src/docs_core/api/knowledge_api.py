"""知识库管理 API"""
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import sqlite3
from pathlib import Path


class KnowledgeNode(BaseModel):
    """知识库节点"""
    id: str
    title: str
    type: str  # 'folder' | 'document'
    parent_id: Optional[str] = None
    visible: bool = False
    library_id: str
    file_path: Optional[str] = None
    status: str = 'pending'  # pending | processing | completed | failed
    sort_order: int = 0
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class KnowledgeLibrary(BaseModel):
    """知识库"""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class KnowledgeService:
    """知识库服务"""

    def __init__(self):
        self.nodes: List[KnowledgeNode] = []
        self.libraries: List[KnowledgeLibrary] = []
        self.db_path = self._resolve_db_path()
        self._init_db()
        self._load_from_db()

    def _resolve_db_path(self) -> Path:
        root_dir = Path(__file__).resolve().parents[5]
        data_dir = root_dir / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / 'knowledge.sqlite3'

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS libraries (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    parent_id TEXT,
                    visible INTEGER NOT NULL,
                    library_id TEXT NOT NULL,
                    file_path TEXT,
                    status TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            conn.commit()

    def _load_from_db(self) -> None:
        with self._get_conn() as conn:
            lib_rows = conn.execute(
                'SELECT id, name, description, created_at, updated_at FROM libraries ORDER BY created_at ASC'
            ).fetchall()
            node_rows = conn.execute(
                '''
                SELECT id, title, type, parent_id, visible, library_id, file_path, status, sort_order, created_at, updated_at
                FROM nodes
                ORDER BY library_id ASC, parent_id ASC, sort_order ASC, created_at ASC
                '''
            ).fetchall()
        self.libraries = [
            KnowledgeLibrary(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
            for row in lib_rows
        ]
        self.nodes = [
            KnowledgeNode(
                id=row['id'],
                title=row['title'],
                type=row['type'],
                parent_id=row['parent_id'],
                visible=bool(row['visible']),
                library_id=row['library_id'],
                file_path=row['file_path'],
                status=row['status'],
                sort_order=int(row['sort_order'] or 0),
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
            for row in node_rows
        ]

    def _upsert_library(self, library: KnowledgeLibrary) -> None:
        with self._get_conn() as conn:
            conn.execute(
                '''
                INSERT INTO libraries (id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    updated_at=excluded.updated_at
                ''',
                (
                    library.id,
                    library.name,
                    library.description,
                    library.created_at.isoformat(),
                    library.updated_at.isoformat()
                )
            )
            conn.commit()

    def _upsert_node(self, node: KnowledgeNode) -> None:
        with self._get_conn() as conn:
            conn.execute(
                '''
                INSERT INTO nodes (id, title, type, parent_id, visible, library_id, file_path, status, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    type=excluded.type,
                    parent_id=excluded.parent_id,
                    visible=excluded.visible,
                    library_id=excluded.library_id,
                    file_path=excluded.file_path,
                    status=excluded.status,
                    sort_order=excluded.sort_order,
                    updated_at=excluded.updated_at
                ''',
                (
                    node.id,
                    node.title,
                    node.type,
                    node.parent_id,
                    1 if node.visible else 0,
                    node.library_id,
                    node.file_path,
                    node.status,
                    node.sort_order,
                    node.created_at.isoformat(),
                    node.updated_at.isoformat()
                )
            )
            conn.commit()

    def _delete_nodes(self, node_ids: List[str]) -> None:
        if not node_ids:
            return
        placeholders = ','.join(['?'] * len(node_ids))
        with self._get_conn() as conn:
            conn.execute(f'DELETE FROM nodes WHERE id IN ({placeholders})', node_ids)
            conn.commit()

    def list_libraries(self) -> List[KnowledgeLibrary]:
        """获取知识库列表"""
        return self.libraries

    def create_library(self, name: str, description: str = '') -> KnowledgeLibrary:
        """创建知识库"""
        library = KnowledgeLibrary(
            id=f'lib-{len(self.libraries) + 1}',
            name=name,
            description=description
        )
        self.libraries.append(library)
        self._upsert_library(library)
        return library

    def get_library(self, library_id: str) -> Optional[KnowledgeLibrary]:
        """获取知识库"""
        for lib in self.libraries:
            if lib.id == library_id:
                return lib
        return None

    def list_nodes(self, library_id: str, visible: bool = False) -> List[KnowledgeNode]:
        """获取知识库节点列表"""
        nodes = [n for n in self.nodes if n.library_id == library_id]
        if visible:
            nodes = [n for n in nodes if n.visible]
        return sorted(nodes, key=lambda n: ((n.parent_id or ''), n.sort_order, n.created_at))

    def create_node(self, node: KnowledgeNode) -> KnowledgeNode:
        """创建节点"""
        sibling_orders = [
            n.sort_order for n in self.nodes
            if n.library_id == node.library_id and n.parent_id == node.parent_id
        ]
        if node.sort_order < 0:
            node.sort_order = 0
        if not sibling_orders and node.sort_order == 0:
            pass
        elif node.sort_order == 0:
            node.sort_order = max(sibling_orders, default=-1) + 1
        self.nodes.append(node)
        self._upsert_node(node)
        return node

    def update_node(self, node_id: str, **kwargs) -> Optional[KnowledgeNode]:
        """更新节点"""
        for node in self.nodes:
            if node.id == node_id:
                old_parent_id = node.parent_id
                old_library_id = node.library_id
                for key, value in kwargs.items():
                    if hasattr(node, key):
                        setattr(node, key, value)
                has_explicit_sort_order = 'sort_order' in kwargs
                parent_or_library_changed = (
                    old_parent_id != node.parent_id or old_library_id != node.library_id
                )
                if ('parent_id' in kwargs or 'library_id' in kwargs) and not has_explicit_sort_order:
                    sibling_orders = [
                        n.sort_order for n in self.nodes
                        if n.id != node.id and n.library_id == node.library_id and n.parent_id == node.parent_id
                    ]
                    node.sort_order = max(sibling_orders, default=-1) + 1
                if parent_or_library_changed:
                    self._normalize_sibling_orders(old_library_id, old_parent_id)
                    if not has_explicit_sort_order:
                        self._normalize_sibling_orders(node.library_id, node.parent_id)
                node.updated_at = datetime.now()
                self._upsert_node(node)
                return node
        return None

    def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        node_ids = {node.id for node in self.nodes}
        if node_id not in node_ids:
            return False
        target = self.get_node(node_id)
        to_delete = {node_id}
        changed = True
        while changed:
            changed = False
            for node in self.nodes:
                if node.parent_id in to_delete and node.id not in to_delete:
                    to_delete.add(node.id)
                    changed = True
        self.nodes = [node for node in self.nodes if node.id not in to_delete]
        self._delete_nodes(list(to_delete))
        if target:
            self._normalize_sibling_orders(target.library_id, target.parent_id)
        return True

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def _normalize_sibling_orders(self, library_id: str, parent_id: Optional[str]) -> None:
        siblings = sorted(
            [n for n in self.nodes if n.library_id == library_id and n.parent_id == parent_id],
            key=lambda n: (n.sort_order, n.created_at)
        )
        for idx, sibling in enumerate(siblings):
            if sibling.sort_order != idx:
                sibling.sort_order = idx
                sibling.updated_at = datetime.now()
                self._upsert_node(sibling)


knowledge_service = KnowledgeService()
