import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.shared.data_paths import get_history_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    conn = sqlite3.connect(get_history_db())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                model TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)")


def create_conversation(query: str, answer: str, sources: list, model: str = "") -> dict:
    conv_id = uuid.uuid4().hex
    now = _now()
    title = (query or "").strip()[:50] or "新对话"
    with _db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, "user", query, None, None, now),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, "assistant", answer, json.dumps(sources or [], ensure_ascii=False), model, now),
        )
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations(limit: int = 50) -> list:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conv_id: str):
    with _db() as conn:
        conv = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
        if conv is None:
            return None
        rows = conn.execute(
            "SELECT role, content, sources, model, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conv_id,),
        ).fetchall()
    messages = []
    for r in rows:
        m = dict(r)
        m["sources"] = json.loads(m["sources"]) if m["sources"] else []
        messages.append(m)
    return {
        "id": conv["id"],
        "title": conv["title"],
        "created_at": conv["created_at"],
        "updated_at": conv["updated_at"],
        "messages": messages,
    }


def delete_conversation(conv_id: str) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return cur.rowcount > 0
