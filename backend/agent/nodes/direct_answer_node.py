from backend.agent.agent_state import AgentState

"悬空的直接回答节点，将文档内容清空，再让generate节点回答"

async def direct_answer_node(state: AgentState) -> dict:
    return {"documents": []}
