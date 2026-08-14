import json

from backend.shared.clients import LLMClient
from backend.agent.agent_state import AgentState

EVALUATE_SYSTEM_PROMPT = """你是一个建筑规范检索质量评估专家。
你需要评估检索到的文档片段是否足以回答用户问题。

评估标准：
- "sufficient": 文档包含了回答问题所需的关键信息（具体条款、数值、等级等）
- "insufficient": 文档太少或完全不相关，需要用扩展查询再试

请只输出 JSON，格式：{"result": "...", "reason": "..."}"""

KEYWORD_COVERAGE_THRESHOLD = 0.5


def create_evaluate_node(llm_client: LLMClient):
    async def evaluate_node(state: AgentState) -> dict:
        if state.retrieval_count >= state.max_retrieval_attempts:
            return {"evaluation_result": "sufficient"}

        if not state.documents:
            return {"evaluation_result": "insufficient"}

        if state.keywords:
            text_blob = " ".join(d.text for d in state.documents)
            hit_count = sum(1 for kw in state.keywords if kw in text_blob)
            if hit_count / len(state.keywords) < KEYWORD_COVERAGE_THRESHOLD:
                return {"evaluation_result": "insufficient"}

        doc_summary = "\n".join(
            f"[{i+1}][score={d.score:.3f}] {d.text[:250]}..."
            for i, d in enumerate(state.documents[:5])
        )
        user_prompt = f"用户问题：{state.query}\n\n检索到的文档片段：\n{doc_summary}"

        try:
            resp = llm_client.client.chat.completions.create(
                model=llm_client.model,
                messages=[
                    {"role": "system", "content": EVALUATE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=256,
            )
            content = resp.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.strip("`").strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            result = json.loads(content)
        except Exception as e:
            print(f"[evaluate_node] LLM 调用失败: {e}")
            result = {"result": "sufficient", "reason": "LLM 不可用，默认通过"}

        return {"evaluation_result": result.get("result", "sufficient")}

    return evaluate_node
