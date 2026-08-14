import asyncio
from typing import List, Optional

from langgraph.graph import StateGraph, END

from backend.shared.models import RetrievalResult, GeneratedAnswer
from backend.shared.clients import LLMClient, RerankClient
from backend.retrievers.fusion_retriever import FusionRetriever
from backend.query_optimizer.rewriter import QueryRewriter
from backend.query_optimizer.pipeline import QueryOptimizerPipeline
from backend.generator.llm_generator import LLMGenerator
from backend.cache.semantic_cache import SemanticCache
from backend.agent.agent_state import AgentState
from .nodes import (
    create_classify_node,
    direct_answer_node,
    create_optimize_query_node,
    create_retrieve_node,
    create_evaluate_node,
    create_expand_node,
    create_process_documents_node,
    create_generate_node,
)
from backend.agent.routers import (
    route_after_classify,
    route_after_evaluate,
)


class AgenticRAG:
    def __init__(
        self,
        retriever: Optional[FusionRetriever] = None,
        rewriter: Optional[QueryRewriter] = None,
        generator: Optional[LLMGenerator] = None,
        cache: Optional[SemanticCache] = None,
        max_retrieval_attempts: int = 2,
        include_generate: bool = True,
    ):
        self.retriever = retriever or FusionRetriever()
        self.rewriter = rewriter or QueryRewriter()
        self.generator = generator or LLMGenerator()
        self.cache = cache
        self._llm = LLMClient()
        self._reranker = RerankClient()
        self._pipeline = QueryOptimizerPipeline(rewriter=self.rewriter)
        self._max_attempts = max_retrieval_attempts
        self._include_generate = include_generate
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)

        builder.add_node("classify", create_classify_node(self._llm))
        builder.add_node("direct_answer", direct_answer_node)
        builder.add_node("optimize_query", create_optimize_query_node(self._pipeline))
        builder.add_node("retrieve", create_retrieve_node(self.retriever))
        builder.add_node("evaluate", create_evaluate_node(self._llm))
        builder.add_node("expand_query", create_expand_node(self.rewriter))
        builder.add_node("process_documents", create_process_documents_node(self._reranker))

        if self._include_generate:
            builder.add_node("generate", create_generate_node(self.generator))

        builder.set_entry_point("classify")

        builder.add_conditional_edges(
            "classify",
            route_after_classify,
            {
                "direct_answer": "direct_answer",
                "optimize_query": "optimize_query",
            },
        )

        builder.add_edge("optimize_query", "retrieve")
        builder.add_edge("retrieve", "evaluate")

        builder.add_conditional_edges(
            "evaluate",
            route_after_evaluate,
            {
                "process_documents": "process_documents",
                "expand_query": "expand_query",
            },
        )

        builder.add_edge("expand_query", "retrieve")

        if self._include_generate:
            builder.add_edge("process_documents", "generate")
            builder.add_edge("direct_answer", "generate")
            builder.add_edge("generate", END)
        else:
            builder.add_edge("process_documents", END)
            builder.add_edge("direct_answer", END)

        return builder.compile()

    @staticmethod
    def _from_cache(cached: dict) -> dict:
        return {
            "answer": GeneratedAnswer(
                answer=cached["answer"],
                sources=[RetrievalResult(**s) if isinstance(s, dict) else s for s in cached.get("sources", [])],
                from_cache=True,
            ),
            "documents": [],
            "optimized_query": None,
        }

    async def run(self, query: str) -> dict:
        if self.cache:
            cached = self.cache.get(query)
            if cached:
                return self._from_cache(cached)

        locked = False
        if self.cache:
            for _ in range(3):
                if self.cache.acquire_lock(query):
                    locked = True
                    break
                await asyncio.sleep(0.5)
                cached = self.cache.get(query)
                if cached:
                    return self._from_cache(cached)

        try:
            state = AgentState(
                query=query,
                max_retrieval_attempts=self._max_attempts,
            )

            result = await self._graph.ainvoke(state)
            answer: Optional[GeneratedAnswer] = result.get("answer")
            documents: List[RetrievalResult] = result.get("documents", [])

            if self.cache and answer and not answer.from_cache:
                self.cache.set(
                    query=query,
                    answer=answer.answer,
                    sources=[d.__dict__ if hasattr(d, "__dict__") else d for d in documents],
                )

            return result
        finally:
            if self.cache and locked:
                self.cache.release_lock(query)


agent_app = AgenticRAG()
agent_graph = agent_app._graph
