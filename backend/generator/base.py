from abc import ABC, abstractmethod
from typing import List, Optional

from backend.shared.models import RetrievalResult, GeneratedAnswer


class BaseGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        query: str,
        documents: Optional[List[RetrievalResult]] = None,
    ) -> GeneratedAnswer:
        ...
