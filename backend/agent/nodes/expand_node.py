"""查询扩展节点（expand_query）。

当 evaluate 判定检索质量不足时触发：
- 若已有 pending_expansions，则推进 expansion_index，换下一条扩展查询继续检索；
- 否则按需调用 QueryRewriter.expand() 生成扩展查询（仅质量不足时才调用 LLM，非每次请求）。
输出新的查询词给检索节点，用于补救性再检索。
"""

from backend.query_optimizer.rewriter import QueryRewriter
from backend.agent.agent_state import AgentState


def create_expand_node(rewriter: QueryRewriter):
    async def expand_node(state: AgentState) -> dict:
        if state.pending_expansions:
            return {"expansion_index": state.expansion_index + 1}
        search_query = state.query_rewritten or state.query_cleaned or state.query
        expansions = await rewriter.expand(search_query, state.keywords)
        return {
            "pending_expansions": expansions,
            "expansion_index": 1,
        }

    return expand_node
