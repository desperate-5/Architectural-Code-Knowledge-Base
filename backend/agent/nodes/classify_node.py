import json

from backend.shared.clients import LLMClient
from backend.agent.agent_state import AgentState

"意图识别节点"

CLASSIFY_SYSTEM_PROMPT = """你是一个建筑规范助手的意图判断专家。
用户会提出建筑规范相关的问题。请判断：

intent:
   - "chitchat": 简单闲聊、问候、常识性问题（如"你好"、"今天天气怎么样"）
   - "need_retrieval": 需要查阅规范文档的专业问题（如具体数值、条款、等级要求等）

请只输出 JSON，格式：{"intent": "...", "reason": "..."}"""


def create_classify_node(llm_client: LLMClient):
    async def classify_node(state: AgentState) -> dict:
        try:
            resp = llm_client.client.chat.completions.create(
                model=llm_client.model,
                messages=[
                    {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": state.query},
                ],
                temperature=0.1,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content.strip()
            result = json.loads(content)
        except Exception as e:
            print(f"[classify_node] LLM 调用失败: {e}")
            result = {"intent": "need_retrieval", "reason": "LLM 不可用，默认检索"}

        intent = result.get("intent", "need_retrieval")
        return {"intent": intent}

    return classify_node
