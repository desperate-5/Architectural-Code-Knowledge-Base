from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from backend.agent.rag_agent import AgenticRAG

app = FastAPI(title="RAG Agent")
rag = AgenticRAG()


@app.post("/chat")
async def chat(query: str):
    result = await rag.run(query)
    answer = result.get("answer")
    return {
        "answer": answer.answer if answer else "",
        "sources": [s.__dict__ for s in (answer.sources if answer else [])],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8123)
