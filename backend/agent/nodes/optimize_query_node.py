from backend.query_optimizer.pipeline import QueryOptimizerPipeline
from backend.agent.agent_state import AgentState


def create_optimize_query_node(pipeline: QueryOptimizerPipeline):
    async def optimize_query_node(state: AgentState) -> dict:
        opt = await pipeline.run(state.query)
        return {
            "query_cleaned": opt.cleaned,
            "query_rewritten": opt.rewritten or opt.cleaned or state.query,
            "keywords": opt.keywords,
        }

    return optimize_query_node
