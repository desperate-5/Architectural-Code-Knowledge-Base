import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.shared.data_paths import get_history_db

_ALLOWED_FIELDS = {"status", "chunk_size", "chunk_overlap", "chunk_count", "error"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    conn = sqlite3.connect(get_history_db())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                chunk_size INTEGER NOT NULL DEFAULT 512,
                chunk_overlap INTEGER NOT NULL DEFAULT 64,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def create_document(filename: str, chunk_size: int = 512, chunk_overlap: int = 64) -> dict:
    doc_id = uuid.uuid4().hex
    now = _now()
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO documents (id, filename, status, chunk_size, chunk_overlap, chunk_count, error, created_at, updated_at)
            VALUES (?, ?, 'uploaded', ?, ?, 0, NULL, ?, ?)
            """,
            (doc_id, filename, chunk_size, chunk_overlap, now, now),
        )
    return get_document(doc_id)


def list_documents() -> list:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, status, chunk_size, chunk_overlap, chunk_count, error, created_at, updated_at
            FROM documents ORDER BY created_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_document(doc_id: str):
    with _db() as conn:
        row = conn.execute(
            """
            SELECT id, filename, status, chunk_size, chunk_overlap, chunk_count, error, created_at, updated_at
            FROM documents WHERE id = ?
            """,
            (doc_id,),
        ).fetchone()
    return dict(row) if row else None


def update_document(doc_id: str, **fields) -> bool:
    updates = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not updates:
        return False
    updates["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [doc_id]
    with _db() as conn:
        cur = conn.execute(
            f"UPDATE documents SET {assignments} WHERE id = ?",
            values,
        )
        return cur.rowcount > 0


def delete_document(doc_id: str) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return cur.rowcount > 0
