"""SQLite 数据库初始化与查询"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from src.config import DB_PATH, DEDUP_WINDOW_DAYS


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（自动建库建表）"""
    _ensure_dir(DB_PATH)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


# ── Schema ────────────────────────────────────────────

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS processed_items (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    category    TEXT NOT NULL,
    province    TEXT,
    key_numbers TEXT,
    source      TEXT NOT NULL,
    source_url  TEXT,
    relevance_score INTEGER,
    processed_date  DATE NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_briefings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL UNIQUE,
    content_markdown TEXT NOT NULL,
    items_count INTEGER,
    published   BOOLEAN DEFAULT FALSE,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  DATETIME NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    row = conn.execute(
        "SELECT MAX(version) AS v FROM schema_version"
    ).fetchone()
    if row["v"] is None:
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (1, 'Phase 0 初始 schema')"
        )
        conn.commit()


# ── 查询 ──────────────────────────────────────────────

def get_recent_titles(conn: sqlite3.Connection, days: int = DEDUP_WINDOW_DAYS) -> set[str]:
    """返回最近 N 天内已处理条目的标题集合，用于去重"""
    rows = conn.execute(
        "SELECT title FROM processed_items WHERE processed_date >= date('now', ?)",
        (f"-{days} days",),
    ).fetchall()
    return {row["title"] for row in rows}


def get_recent_urls(conn: sqlite3.Connection, days: int = DEDUP_WINDOW_DAYS) -> set[str]:
    """返回最近 N 天内已处理条目的 URL 集合，用于去重"""
    rows = conn.execute(
        "SELECT source_url FROM processed_items WHERE source_url IS NOT NULL AND processed_date >= date('now', ?)",
        (f"-{days} days",),
    ).fetchall()
    return {row["source_url"] for row in rows}


def save_classified_items(conn: sqlite3.Connection, items: Sequence[dict]) -> int:
    """批量保存已分类条目，返回实际插入数量"""
    inserted = 0
    for item in items:
        item_id = _make_id(item["title"], item.get("source", ""))
        try:
            conn.execute(
                """INSERT OR IGNORE INTO processed_items
                   (id, title, summary, category, province, key_numbers,
                    source, source_url, relevance_score, processed_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    item["title"],
                    item["summary"],
                    item["category"],
                    item.get("province"),
                    item.get("key_numbers"),
                    item.get("source", ""),
                    item.get("source_url"),
                    item.get("relevance_score", 0),
                    date.today().isoformat(),
                ),
            )
            inserted += conn.total_changes  # rough count
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def get_today_items(conn: sqlite3.Connection, target_date: date | None = None) -> list[dict]:
    """获取指定日期的已分类条目"""
    d = (target_date or date.today()).isoformat()
    rows = conn.execute(
        "SELECT * FROM processed_items WHERE processed_date = ? ORDER BY relevance_score DESC",
        (d,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_briefing(conn: sqlite3.Connection, target_date: date, markdown: str, items_count: int) -> None:
    """保存日报到归档表"""
    conn.execute(
        """INSERT OR REPLACE INTO daily_briefings (date, content_markdown, items_count)
           VALUES (?, ?, ?)""",
        (target_date.isoformat(), markdown, items_count),
    )
    conn.commit()


def get_briefing(conn: sqlite3.Connection, target_date: date) -> str | None:
    """获取指定日期的日报内容"""
    row = conn.execute(
        "SELECT content_markdown FROM daily_briefings WHERE date = ?",
        (target_date.isoformat(),),
    ).fetchone()
    return row["content_markdown"] if row else None


def list_briefings(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """列出最近 N 天的日报概要"""
    rows = conn.execute(
        """SELECT date, items_count, published, created_at
           FROM daily_briefings
           WHERE date >= date('now', ?)
           ORDER BY date DESC""",
        (f"-{days} days",),
    ).fetchall()
    return [dict(row) for row in rows]


# ── 工具 ──────────────────────────────────────────────

def _make_id(title: str, source: str) -> str:
    """根据标题和来源生成稳定的 ID"""
    import hashlib
    raw = f"{title.strip()}|{source.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
