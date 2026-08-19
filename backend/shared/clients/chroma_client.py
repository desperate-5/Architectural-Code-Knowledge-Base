import chromadb
from backend.shared.settings import Settings


class ChromaClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        settings = Settings()
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self.collection_name = settings.CHROMA_COLLECTION
        self._client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self._client.get_or_create_collection(
            self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_or_create_collection(self, name: str, metadata: dict = None):
        return self._client.get_or_create_collection(name, metadata=metadata)

    def reset(self):
        self._client.delete_collection(self.collection_name)
        self.collection = self._client.get_or_create_collection(
            self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
