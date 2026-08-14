from typing import List

import jieba

from .domain_loader import DomainLoader


class KeywordExtractor:
    def __init__(self):
        self._domain_terms = DomainLoader().terms
        for t in self._domain_terms:
            jieba.add_word(t, freq=100000, tag="n")

    def extract(self, text: str) -> List[str]:
        if not text:
            return []

        tokens = jieba.lcut(text)

        scored: dict[str, float] = {}
        for t in tokens:
            t = t.strip()
            if len(t) < 2:
                continue
            if t in self._domain_terms:
                scored[t] = scored.get(t, 0) + 10.0
            else:
                scored[t] = scored.get(t, 0) + 1.0

        return sorted(scored.keys(), key=lambda k: -scored[k])
