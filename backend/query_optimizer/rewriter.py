from typing import Callable, List, TypeVar

from backend.shared.clients import LLMClient

from .domain_loader import DomainLoader

T = TypeVar("T")


class QueryRewriter:
    def __init__(self):
        llm = LLMClient()
        self._client = llm.client
        self._model = llm.model
        self._domain_categories = DomainLoader().categories

    async def rewrite(self, query: str) -> str:
        return self._try_with_fallback(
            llm_call=lambda: self._call_llm_rewrite(query),
            rule_call=lambda: self._rule_rewrite(query),
        )

    async def expand(self, query: str, keywords: List[str]) -> List[str]:
        return self._try_with_fallback(
            llm_call=lambda: self._call_llm_expand(query, keywords),
            rule_call=lambda: self._rule_expand(query, keywords),
        )

    def _try_with_fallback(
        self,
        llm_call: Callable[[], T],
        rule_call: Callable[[], T],
    ) -> T:
        if self._client:
            try:
                result = llm_call()
                if result:
                    return result
            except Exception as e:
                print(f"[QueryRewriter] LLM 调用失败: {e}")
        return rule_call()

    def _call_llm_rewrite(self, query: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个建筑规范领域的查询改写专家。"
                        "将用户的口语问题改写成适合检索的标准查询语句。"
                        "要求：去除口语化、保留核心术语、补全领域上下文。"
                        "只输出改写后的查询文本，不要解释。\n"
                        "例：「住宅的防火极限是多少？」→「住宅建筑耐火极限」"
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.1,
            max_tokens=64,
        )
        return resp.choices[0].message.content.strip()

    def _rule_rewrite(self, query: str) -> str:
        text = query
        if "建筑" not in text:
            for prefix in ["住宅", "公共", "民用", "高层"]:
                if text.startswith(prefix):
                    text = text.replace(prefix, prefix + "建筑", 1)
                    break
        return text

    def _call_llm_expand(self, query: str, keywords: List[str]) -> List[str]:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是建筑规范查询扩展专家。"
                        "基于用户查询和关键词，生成3个相关扩展查询用于补充检索。"
                        "每行一个，不要序号，不要解释。"
                        "方法：同义替换、上位/下位概念、相关规范术语。\n"
                        "例：query=住宅建筑耐火极限 keywords=耐火极限,住宅 →\n"
                        "居住建筑耐火等级要求\n"
                        "高层住宅防火规范\n"
                        "建筑构件耐火极限"
                    ),
                },
                {
                    "role": "user",
                    "content": f"query={query}\nkeywords={', '.join(keywords)}\n输出：",
                },
            ],
            temperature=0.3,
            max_tokens=128,
        )
        text = resp.choices[0].message.content.strip()
        return [line.strip() for line in text.split("\n") if line.strip()]

    def _rule_expand(self, query: str, keywords: List[str]) -> List[str]:
        if not self._domain_categories or not keywords or not query:
            return []

        related = set()
        for kw in keywords:
            for cat, terms in self._domain_categories.items():
                if cat == "规范用词":
                    continue
                if kw in terms:
                    related.update(terms)
                    break
        related -= set(keywords)
        if not related:
            return []
        return [f"{query} {' '.join(sorted(related)[:5])}"]
