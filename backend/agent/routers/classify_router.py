from backend.agent.agent_state import AgentState


def route_after_classify(state: AgentState) -> str:
    if state.intent == "chitchat":
        return "direct_answer"
    return "optimize_query"
