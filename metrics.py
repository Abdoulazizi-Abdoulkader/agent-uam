"""
Collecte de métriques métier pour l'agent UAM.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List

from app_config import get_config


def _get_connection() -> sqlite3.Connection:
    config = get_config()
    conn = sqlite3.connect(config.metrics_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=3000")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            question TEXT NOT NULL,
            normalized TEXT NOT NULL,
            is_relevant INTEGER NOT NULL,
            response_time_ms INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


def normalize_question(text: str) -> str:
    normalized = " ".join((text or "").strip().lower().split())
    return normalized


def record_question(
    user_id: str,
    question: str,
    is_relevant: bool,
    response_time_ms: int
) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO metrics_questions
        (user_id, question, normalized, is_relevant, response_time_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            question,
            normalize_question(question),
            1 if is_relevant else 0,
            response_time_ms,
            datetime.now().isoformat()
        )
    )
    conn.commit()
    conn.close()


def get_metrics_summary() -> Dict[str, int | float]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(1) as total FROM metrics_questions")
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(1) as count FROM metrics_questions WHERE is_relevant = 0")
    hors_sujet = cursor.fetchone()["count"]
    cursor.execute("SELECT AVG(response_time_ms) as avg_ms FROM metrics_questions")
    avg_ms = cursor.fetchone()["avg_ms"] or 0
    conn.close()
    return {
        "total_questions": int(total),
        "hors_sujet": int(hors_sujet),
        "avg_response_time_ms": round(float(avg_ms), 1)
    }


def get_top_questions(limit: int = 20) -> List[Dict[str, int | str]]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT normalized, COUNT(1) as count
        FROM metrics_questions
        GROUP BY normalized
        ORDER BY count DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"question": row["normalized"], "count": row["count"]} for row in rows]
