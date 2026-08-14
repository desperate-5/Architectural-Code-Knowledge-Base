from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

from backend.shared.models import RetrievalResult, GeneratedAnswer


def _merge_documents(
    current: List[RetrievalResult],
    incoming: List[RetrievalResult],
) -> List[RetrievalResult]:
    incoming_ids = {d.id for d in incoming}
    kept = [d for d in current if d.id not in incoming_ids]
    return kept + incoming


class AgentState(BaseModel):
    query: str
    query_cleaned: Optional[str] = None
    query_rewritten: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    documents: Annotated[List[RetrievalResult], _merge_documents] = Field(default_factory=list)
    retrieval_count: int = 0
    expansion_index: int = 0
    pending_expansions: List[str] = Field(default_factory=list)
    max_retrieval_attempts: int = 2
    answer: Optional[GeneratedAnswer] = None
    error: Optional[str] = None
    intent: str = ""
    evaluation_result: str = ""
