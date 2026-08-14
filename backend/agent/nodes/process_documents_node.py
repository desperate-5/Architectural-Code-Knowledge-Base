from typing import List, Optional

from backend.shared.clients import RerankClient
from backend.shared.models import RetrievalResult
from backend.shared.settings import Settings
from backend.agent.agent_state import AgentState

"""
1.去重：按文档 id 去掉重复项
2.调用 Rerank 模型
3. 回退保护:如果 Rerank 调用失败（API 没配、网络错误等）， try/except 捕获异常并打印日志， 不会让整个图崩溃 ，直接降级为按现有分数排序
4.按重排分数降序排序
"""
def _dedupe(documents: List[RetrievalResult]) -> List[RetrievalResult]:
    seen = set()
    unique = []
    for d in documents:
        if d.id in seen:
            continue
        seen.add(d.id)
        unique.append(d)
    return unique


def create_process_documents_node(reranker: Optional[RerankClient] = None):
    reranker = reranker or RerankClient()

    async def process_documents_node(state: AgentState) -> dict:
        docs = _dedupe(state.documents)
        if not docs:
            return {"documents": docs}
        reranked = False
        try:
            results = reranker.rerank(state.query, [d.text for d in docs], top_n=len(docs))
            for item in results:
                idx = item.index
                if idx < len(docs):
                    docs[idx].score = item.relevance_score
            reranked = True
        except Exception as e:
            print(f"[process_documents_node] Rerank 调用失败: {e}")
        docs = sorted(docs, key=lambda d: d.score, reverse=True)
        if reranked:
            threshold = Settings().RERANK_SCORE_THRESHOLD
            filtered = [d for d in docs if d.score >= threshold]
            docs = filtered if filtered else docs[:1]
        return {"documents": docs}

    return process_documents_node
