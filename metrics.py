"""
Collecte de métriques métier pour l'agent UAM.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional

from app_config import get_config

# Connexion SQLite réutilisée (singleton thread-safe)
_conn: Optional[sqlite3.Connection] = None
_conn_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is None:
            config = get_config()
            _conn = sqlite3.connect(config.metrics_db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.execute("PRAGMA busy_timeout=3000")
            _ensure_tables(_conn)
    return _conn


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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_system (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpu_percent REAL NOT NULL,
            memory_percent REAL NOT NULL,
            memory_used_mb REAL NOT NULL,
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


def get_metrics_summary() -> Dict[str, int | float]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(1) as total FROM metrics_questions")
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(1) as count FROM metrics_questions WHERE is_relevant = 0")
    hors_sujet = cursor.fetchone()["count"]
    cursor.execute("SELECT AVG(response_time_ms) as avg_ms FROM metrics_questions")
    avg_ms = cursor.fetchone()["avg_ms"] or 0
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
    return [{"question": row["normalized"], "count": row["count"]} for row in rows]


def record_system_metrics() -> None:
    """Enregistre l'utilisation CPU et RAM"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO metrics_system (cpu_percent, memory_percent, memory_used_mb, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (cpu, mem.percent, mem.used / (1024 * 1024), datetime.now().isoformat())
        )
        conn.commit()
    except ImportError:
        pass


def get_latest_system_metrics() -> Optional[Dict[str, float]]:
    """Récupère les dernières métriques système enregistrées"""
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT cpu_percent, memory_percent, memory_used_mb FROM metrics_system ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return {
                "cpu_percent": round(row["cpu_percent"], 1),
                "memory_percent": round(row["memory_percent"], 1),
                "memory_used_mb": round(row["memory_used_mb"], 1)
            }
    except sqlite3.OperationalError:
        pass
    return None

