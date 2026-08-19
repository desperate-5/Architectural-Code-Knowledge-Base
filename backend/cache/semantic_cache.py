import hashlib
import json
import time
from typing import Optional

import redis as _redis

from backend.shared.clients import EmbedClient, ChromaClient


class SemanticCache:
    def __init__(
        self,
        similarity_threshold: float = 0.95,
        ttl: int = 3600,
        max_entries: int = 1000,
        redis_url: str = "redis://localhost:6379/0",
        cache_collection: str = "query_cache",
    ):
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self.max_entries = max_entries
        self._redis = _redis.from_url(redis_url, decode_responses=True)
        self._embed_client = EmbedClient()
        self._collection = ChromaClient()._client.get_or_create_collection(
            cache_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def get(self, query: str) -> Optional[dict]:
        # 第一层：Redis 精确命中（O(1)，无需 embedding）
        exact = self._redis.get(f"cache:{self._make_key(query)}")
        if exact is not None:
            data = json.loads(exact)
            data["similarity"] = 1.0
            return data

        # 第二层：ChromaDB 语义命中（ANN 检索 top-1）
        emb = self._embed(query)
        if emb is None:
            return None

        res = self._collection.query(
            query_embeddings=[emb],
            n_results=1,
            include=["metadatas", "distances"],
        )
        if not res["ids"] or not res["ids"][0]:
            return None

        distance = res["distances"][0][0]
        similarity = 1.0 - distance
        if similarity < self.similarity_threshold:
            return None

        meta = res["metadatas"][0][0]
        return {
            "query": meta.get("query", ""),
            "answer": meta.get("answer", ""),
            "sources": json.loads(meta.get("sources", "[]")),
            "similarity": similarity,
        }

    def set(self, query: str, answer: str, sources: Optional[list] = None):
        key = self._make_key(query)
        # 写 Redis 精确层（短 TTL 自动过期）
        self._redis.set(
            f"cache:{key}",
            json.dumps({"query": query, "answer": answer, "sources": sources or []}),
            ex=self.ttl,
        )

        # 写 ChromaDB 语义层
        emb = self._embed(query)
        if emb is None:
            return
        self._collection.upsert(
            ids=[key],
            embeddings=[emb],
            documents=[query],
            metadatas=[{
                "query": query,
                "answer": answer,
                "sources": json.dumps(sources or []),
                "timestamp": str(int(time.time())),
            }],
        )

        # 容量管理：ChromaDB 无内置逐出，按 timestamp 超限清理
        while self._collection.count() > self.max_entries:
            self._evict_oldest()

    def acquire_lock(self, query: str, timeout: int = 30) -> bool:
        return bool(self._redis.set(
            f"lock:{self._make_key(query)}", "1", nx=True, ex=timeout
        ))

    def release_lock(self, query: str):
        self._redis.delete(f"lock:{self._make_key(query)}")

    def clear(self):
        exact_keys = self._redis.keys("cache:*")
        if exact_keys:
            self._redis.delete(*exact_keys)
        lock_keys = self._redis.keys("lock:*")
        if lock_keys:
            self._redis.delete(*lock_keys)
        ids = self._collection.get()["ids"]
        if ids:
            self._collection.delete(ids=ids)

    def stats(self) -> dict:
        return {
            "entries": self._collection.count(),
            "exact_entries": len(self._redis.keys("cache:*")),
            "config": {
                "backend": "redis_exact + chromadb_semantic",
                "similarity_threshold": self.similarity_threshold,
                "ttl": self.ttl,
                "max_entries": self.max_entries,
            },
        }

    def _embed(self, text: str) -> Optional[list[float]]:
        try:
            return self._embed_client.get_embedding(text)
        except Exception as e:
            print(f"[SemanticCache] embedding 失败: {e}")
            return None

    @staticmethod
    def _make_key(query: str) -> str:
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    def _evict_oldest(self):
        res = self._collection.get(include=["metadatas"])
        if not res["ids"]:
            return
        oldest = min(
            zip(res["ids"], res["metadatas"]),
            key=lambda x: float(x[1].get("timestamp", "0") or 0),
        )[0]
        self._collection.delete(ids=[oldest])
