from backend.agent.agent_state import AgentState


def route_after_evaluate(state: AgentState) -> str:
    if state.evaluation_result == "sufficient":
        return "process_documents"
    return "expand_query"
