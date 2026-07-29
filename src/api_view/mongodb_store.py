"""
MongoDB 持久化 Store（替代 InMemoryStore）

基于 LangGraph BaseStore 接口，使用 MongoDB 作为后端存储。
支持用户偏好、技能持久化等跨会话数据的持久化存储。

设计：
- 继承 BaseStore，实现 put/get/search/delete 接口
- 使用 pymongo 同步客户端（LangGraph store 需要同步接口）
- 数据格式：每个 namespace + key 组合为一条 MongoDB 文档
- 支持 TTL（可选）
"""
import json
from typing import Any, Optional, Sequence
from datetime import datetime

from pymongo import MongoClient
from langgraph.store.base import BaseStore, Item, Op

from ..log_utils import web_logger


class MongoDBStore(BaseStore):
    """
    MongoDB 持久化 Store

    数据存储格式：
    {
        "_id": "namespace_tuple::key",
        "namespace": ["tuple", "of", "strings"],
        "key": "item_key",
        "value": { ... },  # 任意 JSON-serializable 值
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    """

    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "erp_agent",
        collection_name: str = "langgraph_store",
    ):
        super().__init__()
        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[db_name]
        self._collection = self._db[collection_name]

        # 创建索引
        self._collection.create_index([("namespace", 1), ("key", 1)], unique=True)
        self._collection.create_index("updated_at")

        web_logger.info(
            f"MongoDBStore initialized: {db_name}.{collection_name}"
        )

    def _namespace_key(self, namespace: tuple[str, ...], key: str) -> str:
        """生成唯一文档 ID"""
        ns_str = "::".join(namespace)
        return f"{ns_str}::{key}"

    # ============================================================
    # 核心 CRUD 接口
    # ============================================================

    def get(self, namespace: tuple[str, ...], key: str) -> Optional[Item]:
        """获取单个存储项"""
        doc_id = self._namespace_key(namespace, key)
        doc = self._collection.find_one({"_id": doc_id})
        if doc is None:
            return None
        return self._doc_to_item(doc)

    def put(self, namespace: tuple[str, ...], key: str, value: Any) -> Item:
        """写入/更新存储项"""
        doc_id = self._namespace_key(namespace, key)
        now = datetime.now().isoformat()

        doc = {
            "_id": doc_id,
            "namespace": list(namespace),
            "key": key,
            "value": self._serialize_value(value),
            "created_at": now,
            "updated_at": now,
        }

        # Upsert（保留 created_at）
        self._collection.update_one(
            {"_id": doc_id},
            {
                "$set": {
                    "namespace": list(namespace),
                    "key": key,
                    "value": self._serialize_value(value),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        return Item(
            namespace=namespace,
            key=key,
            value=value,
        )

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        filter: Optional[dict] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Item]:
        """搜索存储项（按 namespace 前缀匹配）"""
        query = {"namespace": {"$regex": f"^{self._ns_prefix_pattern(namespace_prefix)}"}}

        if filter:
            # 简单值过滤
            for k, v in filter.items():
                query[f"value.{k}"] = v

        cursor = (
            self._collection.find(query)
            .sort("updated_at", -1)
            .skip(offset)
            .limit(limit)
        )

        return [self._doc_to_item(doc) for doc in cursor]

    def delete(self, namespace: tuple[str, ...], key: str) -> None:
        """删除存储项"""
        doc_id = self._namespace_key(namespace, key)
        self._collection.delete_one({"_id": doc_id})

    def list_namespaces(
        self,
        *,
        prefix: Optional[tuple[str, ...]] = None,
        max_depth: Optional[int] = None,
    ) -> list[tuple[str, ...]]:
        """列出所有 namespace"""
        query = {}
        if prefix:
            query = {"namespace": {"$regex": f"^{self._ns_prefix_pattern(prefix)}"}}

        namespaces = set()
        for doc in self._collection.find(query, {"namespace": 1}):
            ns = tuple(doc.get("namespace", []))
            if max_depth:
                ns = ns[:max_depth]
            namespaces.add(ns)

        return sorted(namespaces)

    # ============================================================
    # 异步接口（委托给同步实现）
    # ============================================================

    async def aget(self, namespace: tuple[str, ...], key: str) -> Optional[Item]:
        return self.get(namespace, key)

    async def aput(self, namespace: tuple[str, ...], key: str, value: Any) -> Item:
        return self.put(namespace, key, value)

    async def asearch(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        filter: Optional[dict] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Item]:
        return self.search(namespace_prefix, filter=filter, limit=limit, offset=offset)

    async def adelete(self, namespace: tuple[str, ...], key: str) -> None:
        return self.delete(namespace, key)

    async def alist_namespaces(
        self,
        *,
        prefix: Optional[tuple[str, ...]] = None,
        max_depth: Optional[int] = None,
    ) -> list[tuple[str, ...]]:
        return self.list_namespaces(prefix=prefix, max_depth=max_depth)

    # ============================================================
    # 批量接口
    # ============================================================

    def batch(self, ops: Sequence[Op]) -> list[Any]:
        """批量操作"""
        results = []
        for op in ops:
            if op[0] == "get":
                results.append(self.get(op[1], op[2]))
            elif op[0] == "put":
                results.append(self.put(op[1], op[2], op[3]))
            elif op[0] == "search":
                results.append(self.search(op[1], **op[2] if len(op) > 2 else {}))
            elif op[0] == "delete":
                self.delete(op[1], op[2])
                results.append(None)
            else:
                results.append(None)
        return results

    async def abatch(self, ops: Sequence[Op]) -> list[Any]:
        return self.batch(ops)

    # ============================================================
    # 内部工具
    # ============================================================

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """序列化值（确保 JSON 兼容）"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return value
        if isinstance(value, (list, tuple)):
            return list(value)
        # 其他类型转为字符串
        return str(value)

    @staticmethod
    def _doc_to_item(doc: dict) -> Item:
        """将 MongoDB 文档转为 Item"""
        namespace = tuple(doc.get("namespace", []))
        return Item(
            namespace=namespace,
            key=doc.get("key", ""),
            value=doc.get("value"),
        )

    @staticmethod
    def _ns_prefix_pattern(prefix: tuple[str, ...]) -> str:
        """生成 namespace 前缀正则表达式"""
        escaped = [p.replace(".", "\\.").replace("[", "\\[").replace("]", "\\]") for p in prefix]
        return "^" + "\\.".join(escaped) if escaped else ""

    def close(self):
        """关闭 MongoDB 连接"""
        if self._client:
            self._client.close()
            self._client = None
