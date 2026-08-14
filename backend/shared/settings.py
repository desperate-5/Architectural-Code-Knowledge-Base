import os

from dotenv import load_dotenv

from backend.shared.data_paths import get_project_root, get_chroma_dir

dotenv_path = os.path.join(get_project_root(), ".env")
load_dotenv(dotenv_path)


class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        self.DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

        self.EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
        self.EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")

        self.RERANK_API_KEY = os.getenv("RERANK_API_KEY") or os.getenv("EMBEDDING_API_KEY")
        self.RERANK_API_BASE = os.getenv("RERANK_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3-rerank")
        self.RERANK_SCORE_THRESHOLD = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.5"))

        self.MINERU_API_TOKEN = os.getenv("MINERU_API_TOKEN")
        self.MINERU_API_BASE = os.getenv("MINERU_API_BASE", "https://mineru.net/api/v4")
        self.MINERU_MODEL_VERSION = os.getenv("MINERU_MODEL_VERSION", "vlm")

        self.NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        self.NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

        self.CHROMA_PERSIST_DIR = os.getenv(
            "CHROMA_PERSIST_DIR",
            get_chroma_dir(),
        )
        self.CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "pdf_documents")
