"""研究缓存 — SQLite 存储搜索结果和会话"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.config import CACHE_DB_PATH, CACHE_TTL_HOURS


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_cache_connection() -> sqlite3.Connection:
    """获取缓存数据库连接（自动建库建表）"""
    _ensure_dir(CACHE_DB_PATH)
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS search_cache (
    id          TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id          TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running',
    search_queries_json TEXT,
    sources_count INTEGER DEFAULT 0,
    output_dir  TEXT,
    report_path TEXT,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now')),
    completed_at DATETIME
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


# ── 搜索缓存 ──────────────────────────────────────────

def _make_cache_id(query: str) -> str:
    return hashlib.sha256(query.strip().encode()).hexdigest()[:16]


def get_cached_search(conn: sqlite3.Connection, query: str) -> list[dict] | None:
    """查找缓存的搜索结果，过期则返回 None"""
    cache_id = _make_cache_id(query)
    row = conn.execute(
        "SELECT results_json, created_at FROM search_cache WHERE id = ?",
        (cache_id,),
    ).fetchone()

    if not row:
        return None

    created = datetime.fromisoformat(row["created_at"])
    age_hours = (datetime.now() - created).total_seconds() / 3600
    if age_hours > CACHE_TTL_HOURS:
        conn.execute("DELETE FROM search_cache WHERE id = ?", (cache_id,))
        conn.commit()
        return None

    return json.loads(row["results_json"])


def save_search_cache(conn: sqlite3.Connection, query: str, results: list[dict]) -> None:
    """保存搜索结果到缓存"""
    cache_id = _make_cache_id(query)
    conn.execute(
        "INSERT OR REPLACE INTO search_cache (id, query, results_json) VALUES (?, ?, ?)",
        (cache_id, query, json.dumps(results, ensure_ascii=False)),
    )
    conn.commit()


# ── 研究会话 ──────────────────────────────────────────

def _make_session_id(query: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(query.encode()).hexdigest()[:6]
    return f"{ts}_{short_hash}"


def create_session(conn: sqlite3.Connection, query: str) -> str:
    """创建研究会话，返回会话 ID"""
    session_id = _make_session_id(query)
    conn.execute(
        "INSERT INTO research_sessions (id, query) VALUES (?, ?)",
        (session_id, query),
    )
    conn.commit()
    return session_id


def update_session(
    conn: sqlite3.Connection,
    session_id: str,
    *,
    status: str | None = None,
    search_queries: list[str] | None = None,
    sources_count: int | None = None,
    output_dir: str | None = None,
    report_path: str | None = None,
) -> None:
    """更新会话状态"""
    updates = []
    params = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status == "completed":
            updates.append("completed_at = datetime('now')")

    if search_queries is not None:
        updates.append("search_queries_json = ?")
        params.append(json.dumps(search_queries, ensure_ascii=False))

    if sources_count is not None:
        updates.append("sources_count = ?")
        params.append(sources_count)

    if output_dir is not None:
        updates.append("output_dir = ?")
        params.append(output_dir)

    if report_path is not None:
        updates.append("report_path = ?")
        params.append(report_path)

    if not updates:
        return

    params.append(session_id)
    conn.execute(
        f"UPDATE research_sessions SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()


def list_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """列出最近的研究会话"""
    rows = conn.execute(
        "SELECT * FROM research_sessions ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_session(conn: sqlite3.Connection, session_id: str) -> dict | None:
    """获取指定会话"""
    row = conn.execute(
        "SELECT * FROM research_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None
