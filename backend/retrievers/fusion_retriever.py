from typing import List, Optional

from backend.shared.models import RetrievalResult
from backend.retrievers.chroma_retriever import ChromaRetriever
from backend.retrievers.keyword_retriever import KeywordRetriever

K = 60


def _rrf_score(rank: int) -> float:
    return 1.0 / (K + rank)


class FusionRetriever:
    def __init__(
        self,
        fusion_top_k: int = 10,
        vector_top_k: int = 10,
        keyword_top_k: int = 10,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
    ):
        self.vector = ChromaRetriever()
        self.keyword = KeywordRetriever()
        self.fusion_top_k = fusion_top_k
        self.vector_top_k = vector_top_k
        self.keyword_top_k = keyword_top_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        query_cleaned: Optional[str] = None,
        query_rewritten: Optional[str] = None,
    ) -> List[RetrievalResult]:
        vector_results = await self.vector.retrieve(query_cleaned or query, self.vector_top_k)
        keyword_results = await self.keyword.retrieve(query_rewritten or query, self.keyword_top_k)

        fusion_map: dict[str, RetrievalResult] = {}
        score_map: dict[str, float] = {}

        channels = [
            (vector_results, "vector", self.vector_weight),
            (keyword_results, "keyword", self.keyword_weight),
        ]

        for results, channel_name, weight in channels:
            for rank, r in enumerate(results, start=1):
                if r.id in fusion_map:
                    fusion_map[r.id].metadata["_sources"].append(channel_name)
                else:
                    r.metadata["_sources"] = [channel_name]
                    fusion_map[r.id] = r
                score_map[r.id] = score_map.get(r.id, 0) + _rrf_score(rank) * weight

        fused = sorted(
            fusion_map.values(),
            key=lambda r: -score_map.get(r.id, 0),
        )[:self.fusion_top_k]

        for r in fused:
            r.score = score_map.get(r.id, 0)

        return fused[:top_k]
