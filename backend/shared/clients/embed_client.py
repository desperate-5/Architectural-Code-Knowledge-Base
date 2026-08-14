from openai import OpenAI
from backend.shared.settings import Settings


class EmbedClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        settings = Settings()
        self.client = OpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_API_BASE,
        )
        self.model = settings.EMBEDDING_MODEL

    def get_embedding(self, text: str):
        return (
            self.client.embeddings.create(input=[text], model=self.model)
            .data[0]
            .embedding
        )

    def get_embeddings(self, texts: list[str]):
        resp = self.client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in resp.data]
