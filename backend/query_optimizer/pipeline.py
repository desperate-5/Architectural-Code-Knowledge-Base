from .base import OptimizedQuery
from .cleaner import clean_query
from .keyword_extractor import KeywordExtractor
from .rewriter import QueryRewriter


class QueryOptimizerPipeline:
    def __init__(self, rewriter: QueryRewriter | None = None):
        self._keyword_extractor = KeywordExtractor()
        self._rewriter = rewriter or QueryRewriter()

    async def run(self, query: str) -> OptimizedQuery:
        cleaned = clean_query(query)
        keywords = self._keyword_extractor.extract(cleaned)
        rewritten = await self._rewriter.rewrite(cleaned)
        return OptimizedQuery(
            original=query,
            cleaned=cleaned,
            keywords=keywords,
            rewritten=rewritten,
        )
