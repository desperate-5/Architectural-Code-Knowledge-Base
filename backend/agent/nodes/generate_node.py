from backend.generator.llm_generator import LLMGenerator
from backend.agent.agent_state import AgentState


def create_generate_node(generator: LLMGenerator):
    async def generate_node(state: AgentState) -> dict:
        result = await generator.generate(
            query=state.query,
            documents=state.documents,
        )
        return {"answer": result}

    return generate_node
