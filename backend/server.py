from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from backend.agent.rag_agent import AgenticRAG
from backend.cache.semantic_cache import SemanticCache

app = FastAPI(title="RAG Agent")

try:
    rag = AgenticRAG(cache=SemanticCache())
    print("[server] 语义缓存已启用 (Redis 精确层 + ChromaDB 语义层)")
except Exception as e:
    print(f"[server] 语义缓存初始化失败,本次运行禁用缓存: {e}")
    rag = AgenticRAG()


@app.post("/chat")
async def chat(query: str):
    result = await rag.run(query)
    answer = result.get("answer")
    return {
        "answer": answer.answer if answer else "",
        "sources": [s.__dict__ for s in (answer.sources if answer else [])],
        "from_cache": bool(getattr(answer, "from_cache", False)),
        "cache_similarity": getattr(answer, "cache_similarity", None) or 0.0,
        "model": getattr(answer, "model", ""),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8123)
