from backend.retrievers.fusion_retriever import FusionRetriever
from backend.agent.agent_state import AgentState


def _get_search_query(state: AgentState) -> str:
    is_expansion = (
        state.expansion_index > 0
        and state.pending_expansions
        and state.expansion_index <= len(state.pending_expansions)
    )
    if is_expansion:
        return state.pending_expansions[state.expansion_index - 1]
    return state.query_rewritten or state.query_cleaned or state.query


def create_retrieve_node(retriever: FusionRetriever):
    async def retrieve_node(state: AgentState) -> dict:
        search_query = _get_search_query(state)
        docs = await retriever.retrieve(
            search_query,
            top_k=10,
            query_cleaned=state.query_cleaned,
            query_rewritten=state.query_rewritten,
        )
        existing_ids = {d.id for d in state.documents}
        unique_docs = [d for d in docs if d.id not in existing_ids]
        return {
            "documents": unique_docs,
            "retrieval_count": state.retrieval_count + 1,
        }

    return retrieve_node
