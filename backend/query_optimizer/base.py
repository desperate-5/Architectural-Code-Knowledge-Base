from pydantic import BaseModel, Field
from typing import List


class OptimizedQuery(BaseModel):
    original: str
    cleaned: str = ""
    keywords: list[str] = Field(default_factory=list)
    rewritten: str = ""
