import hashlib
from typing import List, Optional
from backend.shared.clients import ChromaClient, EmbedClient
from .base import BaseRetriever
from backend.shared.models import RetrievalResult


class ChromaRetriever(BaseRetriever):
    def __init__(
        self,
        chroma: Optional[ChromaClient] = None,
        embed: Optional[EmbedClient] = None,
    ):
        self._chroma = chroma or ChromaClient()
        self._embed = embed or EmbedClient()
        self._collection = self._chroma.collection

    async def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        query_embedding = self._embed.get_embedding(query)

        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        if not raw["documents"] or not raw["documents"][0]:
            return []

        results = []
        for i, text in enumerate(raw["documents"][0]):
            node_id = hashlib.md5(text.encode()).hexdigest()[:12]
            distance = raw["distances"][0][i] if raw.get("distances") else 0.0
            score = 1.0 - distance / 2.0
            results.append(RetrievalResult(
                id=node_id,
                text=text,
                score=score,
                source_type="vector",
                metadata=raw["metadatas"][0][i] if raw.get("metadatas") else {},
            ))

        return results
