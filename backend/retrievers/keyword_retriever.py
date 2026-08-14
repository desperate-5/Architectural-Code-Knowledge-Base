import os
import sys
import json
import hashlib
from typing import List

import jieba
from whoosh.analysis import Tokenizer, Token, LowercaseFilter
from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from whoosh.scoring import BM25F

from backend.shared.data_paths import get_index_dir
from .base import BaseRetriever
from backend.shared.models import RetrievalResult


class ChineseTokenizer(Tokenizer):
    def __call__(self, text, **kwargs):
        tokens = jieba.lcut(text)
        for t in tokens:
            if t.strip():
                yield Token(original=t, text=t, pos=0, startpos=0, endpos=0, boost=1.0)


def ChineseAnalyzer():
    return ChineseTokenizer() | LowercaseFilter()


for target in ("__main__", "backend.retrievers.keyword_retriever"):
    if target in sys.modules:
        sys.modules[target].ChineseTokenizer = ChineseTokenizer
        sys.modules[target].ChineseAnalyzer = ChineseAnalyzer


INDEX_DIR = get_index_dir()


class KeywordRetriever(BaseRetriever):
    def __init__(self):
        meta_path = os.path.join(INDEX_DIR, "domain_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for term in meta.get("domain_terms", []):
                jieba.add_word(term, freq=100000, tag="n")
        self._ix = open_dir(INDEX_DIR)

    async def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        results = []
        with self._ix.searcher(weighting=BM25F()) as searcher:
            parser = QueryParser("text", schema=self._ix.schema)
            parsed_query = parser.parse(query)
            hits = searcher.search(parsed_query, limit=top_k)

            for hit in hits:
                text = hit["text"]
                articles_raw = hit.get("articles", "[]")
                try:
                    articles = json.loads(articles_raw)
                except (json.JSONDecodeError, TypeError):
                    articles = []

                rid = hashlib.md5(text.encode()).hexdigest()[:12]
                results.append(RetrievalResult(
                    id=rid,
                    text=text,
                    score=float(hit.score),
                    source_type="keyword",
                    metadata={
                        "filename": hit.get("filename", ""),
                        "chapter": hit.get("chapter", ""),
                        "section": hit.get("section", ""),
                        "articles": articles,
                    },
                ))

        return results
