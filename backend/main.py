import asyncio
import json
import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent import AgenticRAG
from backend.agent.agent_state import AgentState
from backend.history import store as history_store
from backend.graph.service import service as graph_service
from backend.documents import store as documents_store
from backend.indexing import build_service
from backend.shared.data_paths import get_documents_dir, get_parsed_dir

from backend.retrievers.keyword_retriever import ChineseTokenizer, ChineseAnalyzer

for mod_name in ("__main__", "__mp_main__", "backend.retrievers.keyword_retriever"):
    if mod_name in sys.modules:
        sys.modules[mod_name].ChineseTokenizer = ChineseTokenizer
        sys.modules[mod_name].ChineseAnalyzer = ChineseAnalyzer


app = FastAPI(title="Agentic RAG API", version="1.0")

history_store.init_db()
documents_store.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent: Optional[AgenticRAG] = None
agent_stream: Optional[AgenticRAG] = None


class AskRequest(BaseModel):
    query: str


class StepInfo(BaseModel):
    node: str
    description: str
    details: dict


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: List[dict]
    model: str
    usage: dict
    steps: List[StepInfo]
    intent: str
    evaluation_result: str


class SaveConversationRequest(BaseModel):
    query: str
    answer: str
    sources: List[dict] = []
    model: str = ""


async def get_agent() -> AgenticRAG:
    global agent
    if agent is None:
        agent = AgenticRAG(max_retrieval_attempts=2)
    return agent


async def get_agent_stream() -> AgenticRAG:
    global agent_stream, agent
    if agent_stream is None:
        await get_agent()
        agent_stream = AgenticRAG(
            max_retrieval_attempts=2,
            include_generate=False,
        )
        agent_stream.generator = agent.generator
    return agent_stream


def reset_agents():
    global agent, agent_stream
    agent = None
    agent_stream = None


build_service.register_on_finished(reset_agents)


GRAPH_STEP_NAMES = {
    "classify": "意图分类 (判断是否需要检索)",
    "direct_answer": "直接回答 (无检索)",
    "optimize_query": "查询优化 (清洗->关键词->改写)",
    "retrieve": "检索 (向量+关键词融合)",
    "evaluate": "检索质量评估",
    "expand_query": "扩展查询 (生成同义/上下位查询)",
    "process_documents": "文档后处理 (排序去重)",
    "generate": "答案生成 (LLM)",
}


def extract_step_details(node_name: str, state: dict) -> dict:
    details = {}
    if node_name == "classify":
        details["intent"] = state.get("intent", "")
    elif node_name in ("retrieve", "process_documents"):
        docs = state.get("documents", [])
        details["document_count"] = len(docs)
        details["top_documents"] = [
            {
                "score": round(d.score, 4),
                "source_type": d.source_type,
                "filename": d.metadata.get("filename", ""),
                "chapter": d.metadata.get("chapter", ""),
                "snippet": d.text[:120].replace("\n", " ").strip(),
            }
            for d in docs[:5]
        ]
    elif node_name == "evaluate":
        details["result"] = state.get("evaluation_result", "")
    elif node_name == "optimize_query":
        details["cleaned"] = state.get("query_cleaned", "")
        details["rewritten"] = state.get("query_rewritten", "")
        details["keywords"] = state.get("keywords", [])
    elif node_name == "expand_query":
        expansions = state.get("pending_expansions", [])
        idx = state.get("expansion_index", 0)
        details["expansions"] = expansions
        details["expansion_index"] = idx
    elif node_name == "generate":
        answer = state.get("answer")
        if answer:
            details["model"] = answer.model
            details["usage"] = answer.usage if answer.usage else {}
    return details


async def run_graph_with_collect(agent: AgenticRAG, query: str):
    initial_state = AgentState(
        query=query,
        max_retrieval_attempts=agent._max_attempts,
    )
    full_state = initial_state.model_dump()
    steps: List[StepInfo] = []

    async for event in agent._graph.astream(full_state, stream_mode="updates"):
        for node_name, node_state in event.items():
            full_state.update(node_state)
            description = GRAPH_STEP_NAMES.get(node_name, node_name)
            details = extract_step_details(node_name, node_state)
            steps.append(StepInfo(node=node_name, description=description, details=details))

    return full_state, steps


async def run_graph_streaming(agent_stream_inst: AgenticRAG, agent_full: AgenticRAG, query: str):
    initial_state = AgentState(
        query=query,
        max_retrieval_attempts=agent_stream_inst._max_attempts,
    )
    full_state = initial_state.model_dump()

    try:
        async for event in agent_stream_inst._graph.astream(full_state, stream_mode="updates"):
            for node_name, node_state in event.items():
                full_state.update(node_state)
                description = GRAPH_STEP_NAMES.get(node_name, node_name)
                details = extract_step_details(node_name, node_state)
                step = StepInfo(node=node_name, description=description, details=details)
                yield f"data: {json.dumps(step.model_dump(), ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'图执行失败: {str(e)}'}, ensure_ascii=False)}\n\n"
        return

    documents = full_state.get("documents", [])
    yield f"data: {json.dumps({'node': 'generate', 'type': 'step', 'description': '答案生成 (流式)', 'details': {}}, ensure_ascii=False)}\n\n"

    try:
        sources_list = []
        full_text = ""
        async for token in agent_full.generator.generate_stream(query=query, documents=documents):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'LLM 生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"
        return

    for s in (documents or []):
        sources_list.append({
            "id": getattr(s, 'id', ''),
            "text": getattr(s, 'text', '')[:500].replace('\n', ' '),
            "score": round(getattr(s, 'score', 0), 4),
            "source_type": getattr(s, 'source_type', ''),
            "channels": getattr(s, 'metadata', {}).get('_sources') or [getattr(s, 'source_type', '')],
            "filename": getattr(s, 'metadata', {}).get('filename', ''),
            "chapter": getattr(s, 'metadata', {}).get('chapter', ''),
        })

    yield f"data: {json.dumps({'type': 'done', 'answer': full_text, 'sources': sources_list, 'model': agent_full.generator._llm.model}, ensure_ascii=False)}\n\n"


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    a = await get_agent()

    full_state, steps = await run_graph_with_collect(a, req.query)

    answer = full_state.get("answer")
    if not answer:
        return AskResponse(
            query=req.query,
            answer="",
            sources=[],
            model="",
            usage={},
            steps=steps,
            intent=full_state.get("intent", ""),
            evaluation_result=full_state.get("evaluation_result", ""),
        )

    sources_list = []
    if hasattr(answer, 'sources') and answer.sources:
        for s in answer.sources:
            sources_list.append({
                "id": s.id if hasattr(s, 'id') else "",
                "text": s.text[:500].replace("\n", " ") if hasattr(s, 'text') else "",
                "score": round(s.score, 4) if hasattr(s, 'score') else 0,
                "source_type": s.source_type if hasattr(s, 'source_type') else "",
                "channels": getattr(s, 'metadata', {}).get("_sources") or [getattr(s, 'source_type', '')],
                "filename": s.metadata.get("filename", "") if hasattr(s, 'metadata') else "",
                "chapter": s.metadata.get("chapter", "") if hasattr(s, 'metadata') else "",
            })

    return AskResponse(
        query=req.query,
        answer=answer.answer,
        sources=sources_list,
        model=answer.model,
        usage=answer.usage if answer.usage else {},
        steps=steps,
        intent=full_state.get("intent", ""),
        evaluation_result=full_state.get("evaluation_result", ""),
    )


@app.post("/ask/stream")
async def ask_stream(req: AskRequest):
    a = await get_agent_stream()
    a_full = await get_agent()
    return StreamingResponse(
        run_graph_streaming(a, a_full, req.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/graph/search")
async def graph_search(q: str = "", limit: int = 20):
    if not q:
        return []
    return graph_service.search_entities(q, limit)


@app.get("/graph/entity")
async def graph_entity(name: str = ""):
    if not name:
        return {"nodes": [], "edges": []}
    return graph_service.get_entity_graph(name)


@app.get("/graph/all")
async def graph_all():
    return graph_service.get_full_graph()


@app.get("/conversations")
async def list_conversations(limit: int = 50):
    return history_store.list_conversations(limit)


@app.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = history_store.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conv


@app.post("/conversations")
async def save_conversation(req: SaveConversationRequest):
    return history_store.create_conversation(req.query, req.answer, req.sources, req.model)


@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if not history_store.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True}


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(64),
):
    filename = (file.filename or "document.pdf").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    doc = documents_store.create_document(filename, chunk_size, chunk_overlap)

    os.makedirs(get_documents_dir(), exist_ok=True)
    pdf_path = os.path.join(get_documents_dir(), f"{doc['id']}.pdf")
    content = await file.read()
    with open(pdf_path, "wb") as f:
        f.write(content)

    return doc


@app.get("/documents")
async def list_documents():
    return documents_store.list_documents()


@app.post("/documents/{doc_id}/build")
async def build_document(doc_id: str):
    if documents_store.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        job_id = build_service.start_build(doc_id)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"job_id": job_id}


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    if documents_store.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="document not found")

    for p in (
        os.path.join(get_documents_dir(), f"{doc_id}.pdf"),
        os.path.join(get_parsed_dir(), f"{doc_id}.chunks.json"),
        os.path.join(get_parsed_dir(), f"{doc_id}.md"),
    ):
        if os.path.exists(p):
            os.remove(p)

    documents_store.delete_document(doc_id)

    try:
        job_id = build_service.start_rebuild_after_delete()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"job_id": job_id}


@app.get("/build/jobs/{job_id}")
async def get_build_job(job_id: str):
    job = build_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
