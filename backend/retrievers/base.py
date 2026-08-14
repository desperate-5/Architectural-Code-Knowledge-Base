from abc import ABC, abstractmethod
from typing import List

from backend.shared.models import RetrievalResult


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        ...
