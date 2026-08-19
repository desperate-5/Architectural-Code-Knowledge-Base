from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RetrievalResult:
    id: str
    text: str
    score: float
    source_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class GeneratedAnswer:
    answer: str
    sources: List[RetrievalResult] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)
    from_cache: bool = False
    cache_similarity: Optional[float] = None
