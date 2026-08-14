import glob
import json
import os
import threading
import uuid

from backend.documents import store as documents_store
from backend.shared.data_paths import get_parsed_dir, get_documents_dir

STAGES = ("parse", "keyword", "vector", "graph")
STAGE_WEIGHTS = {"parse": 0.20, "keyword": 0.10, "vector": 0.15, "graph": 0.55}

_jobs: dict = {}
_lock = threading.Lock()
_active_job_id = None
_on_finished_callbacks = []


def _new_job(job_id: str, doc_id: str | None) -> dict:
    return {
        "job_id": job_id,
        "doc_id": doc_id,
        "status": "running",
        "message": "",
        "overall_percent": 0,
        "stages": {
            stage: {"percent": 0, "current": 0, "total": 0, "message": ""}
            for stage in STAGES
        },
    }


def _compute_overall(job: dict) -> int:
    total = 0.0
    for stage, weight in STAGE_WEIGHTS.items():
        total += weight * job["stages"][stage]["percent"]
    return int(total)


def _make_progress_cb(job_id: str, stage: str):
    def cb(current: int, total: int, message: str = ""):
        job = _jobs.get(job_id)
        if not job:
            return
        percent = int(current / total * 100) if total else 0
        job["stages"][stage] = {
            "percent": percent,
            "current": current,
            "total": total,
            "message": message,
        }
        job["overall_percent"] = _compute_overall(job)
    return cb


def merge_chunks() -> int:
    parsed_dir = get_parsed_dir()
    merged = []
    for path in sorted(glob.glob(os.path.join(parsed_dir, "*.chunks.json"))):
        with open(path, "r", encoding="utf-8") as f:
            merged.extend(json.load(f))
    os.makedirs(parsed_dir, exist_ok=True)
    out_path = os.path.join(parsed_dir, "chunks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return len(merged)


def _call_finished():
    for cb in list(_on_finished_callbacks):
        try:
            cb()
        except Exception:
            pass


def _run_build(job_id: str, doc_id: str | None):
    global _active_job_id
    job = _jobs.get(job_id)
    try:
        if doc_id:
            doc = documents_store.get_document(doc_id)
            if doc is None:
                raise RuntimeError(f"文档不存在: {doc_id}")
            documents_store.update_document(doc_id, status="building", error=None)

            pdf_path = os.path.join(get_documents_dir(), f"{doc_id}.pdf")
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF 文件缺失: {pdf_path}")

            from backend.indexing.parse_pdf import parse_document
            chunk_count = parse_document(
                pdf_path,
                doc_id,
                chunk_size=doc["chunk_size"],
                chunk_overlap=doc["chunk_overlap"],
                progress_callback=_make_progress_cb(job_id, "parse"),
                filename=doc["filename"],
            )
            documents_store.update_document(doc_id, chunk_count=chunk_count)

        merge_chunks()

        from backend.indexing import build_keyword_index
        build_keyword_index.main(progress_callback=_make_progress_cb(job_id, "keyword"))

        from backend.indexing import build_vector_index
        build_vector_index.main(progress_callback=_make_progress_cb(job_id, "vector"))

        from backend.indexing import build_graph_index
        build_graph_index.main(
            write_to_neo4j=False,
            progress_callback=_make_progress_cb(job_id, "graph"),
        )

        from backend.indexing import write_neo4j
        write_neo4j.write_to_neo4j(replace=False)

        if doc_id:
            documents_store.update_document(doc_id, status="indexed", error=None)

        job["status"] = "done"
        job["overall_percent"] = 100
        for stage in STAGES:
            job["stages"][stage]["percent"] = 100
    except Exception as e:
        if doc_id:
            documents_store.update_document(doc_id, status="error", error=str(e))
        if job:
            job["status"] = "error"
            job["message"] = str(e)
    finally:
        if _active_job_id == job_id:
            _active_job_id = None
        _call_finished()


def start_build(doc_id: str) -> str:
    global _active_job_id
    with _lock:
        if _active_job_id and _jobs.get(_active_job_id, {}).get("status") == "running":
            raise RuntimeError("已有构建任务进行中，请稍后再试")
        job_id = uuid.uuid4().hex
        _jobs[job_id] = _new_job(job_id, doc_id)
        _active_job_id = job_id
    threading.Thread(target=_run_build, args=(job_id, doc_id), daemon=True).start()
    return job_id


def start_rebuild_after_delete() -> str:
    global _active_job_id
    with _lock:
        if _active_job_id and _jobs.get(_active_job_id, {}).get("status") == "running":
            raise RuntimeError("已有构建任务进行中，请稍后再试")
        job_id = uuid.uuid4().hex
        _jobs[job_id] = _new_job(job_id, None)
        _active_job_id = job_id
    threading.Thread(target=_run_build, args=(job_id, None), daemon=True).start()
    return job_id


def get_job(job_id: str):
    return _jobs.get(job_id)


def register_on_finished(cb):
    _on_finished_callbacks.append(cb)
