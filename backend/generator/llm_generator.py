from typing import AsyncGenerator, List, Optional
from .base import BaseGenerator
from backend.shared.models import RetrievalResult, GeneratedAnswer
from .prompts import SYSTEM_PROMPT, ANSWER_PROMPT_TEMPLATE, NO_DOC_PROMPT_TEMPLATE
from backend.shared.clients import LLMClient


def _build_answer_prompt(query: str, documents: List[RetrievalResult]) -> str:
    if not documents:
        return _build_no_doc_prompt(query)

    parts = []
    for i, doc in enumerate(documents, start=1):
        source_tag = f"[{i}]"
        header = f"{source_tag} [{doc.source_type}] {doc.metadata.get('chapter', '') or doc.metadata.get('filename', '')}"
        parts.append(f"{header}\n{doc.text}")

    doc_text = "\n\n".join(parts)

    return ANSWER_PROMPT_TEMPLATE.format(doc_text=doc_text, query=query)


def _build_no_doc_prompt(query: str) -> str:
    return NO_DOC_PROMPT_TEMPLATE.format(query=query)


class LLMGenerator(BaseGenerator):
    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        self._llm = llm or LLMClient()
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(
        self,
        query: str,
        documents: Optional[List[RetrievalResult]] = None,
    ) -> GeneratedAnswer:
        prompt = _build_answer_prompt(query, documents or [])
        response = self._call_llm(prompt)

        answer = response.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

        return GeneratedAnswer(
            answer=answer,
            sources=documents or [],
            model=self._llm.model,
            usage=usage,
        )

    async def generate_stream(
        self,
        query: str,
        documents: Optional[List[RetrievalResult]] = None,
    ) -> AsyncGenerator[str, None]:
        prompt = _build_answer_prompt(query, documents or [])
        response = self._llm.client.chat.completions.create(
            model=self._llm.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _call_llm(self, prompt: str):
        return self._llm.client.chat.completions.create(
            model=self._llm.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
