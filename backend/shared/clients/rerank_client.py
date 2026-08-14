import dashscope
from dashscope import TextReRank

from backend.shared.settings import Settings


class RerankClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        settings = Settings()
        self.api_key = settings.RERANK_API_KEY
        self.model = settings.RERANK_MODEL

    def rerank(self, query: str, documents: list[str], top_n: int = 10):
        resp = TextReRank.call(
            model=self.model,
            api_key=self.api_key,
            query=query,
            documents=documents,
            top_n=top_n,
        )
        if resp.status_code != 200:
            raise Exception(f"Rerank failed: {resp.message}")
        return resp.output.results
