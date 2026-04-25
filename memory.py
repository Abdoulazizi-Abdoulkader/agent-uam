"""
Gestion de la mémoire à long terme pour les préférences utilisateur
Stockage transactionnel via SQLite.
"""
import os
import json
import sqlite3
from typing import Dict, Any, List
from datetime import datetime
from logger_config import get_logger
from app_config import get_config

# Logger pour ce module
logger = get_logger(__name__)


class UserMemory:
    """Gestion de la mémoire à long terme pour les préférences utilisateur"""

    def __init__(self, memory_db_path: str | None = None, legacy_json_path: str | None = None):
        config = get_config()
        self.db_path = memory_db_path or config.memory_db_path
        self.legacy_json_path = legacy_json_path or config.memory_file
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=3000")
        self._ensure_tables()
        self._migrate_legacy_json()

    def _ensure_tables(self):
        """Crée les tables si elles n'existent pas."""
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferences_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _migrate_legacy_json(self):
        """Migre l'ancien fichier JSON si présent et DB vide."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(1) as count FROM user_preferences")
            count = cursor.fetchone()["count"]
            if count > 0:
                return
            if not self.legacy_json_path or not os.path.exists(self.legacy_json_path):
                return

            with open(self.legacy_json_path, "r", encoding="utf-8") as f:
                legacy = json.load(f)

            for user_id, data in legacy.items():
                preferences = data.get("preferences", {})
                created_at = data.get("created_at", datetime.now().isoformat())
                last_updated = data.get("last_updated", datetime.now().isoformat())
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO user_preferences
                    (user_id, preferences_json, created_at, last_updated)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, json.dumps(preferences, ensure_ascii=False), created_at, last_updated)
                )

                for conv in data.get("conversation_history", []):
                    cursor.execute(
                        """
                        INSERT INTO user_conversations
                        (user_id, question, response, timestamp)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            conv.get("question", ""),
                            conv.get("response", ""),
                            conv.get("timestamp", datetime.now().isoformat())
                        )
                    )

            self._conn.commit()
            logger.info("Migration de la mémoire JSON vers SQLite effectuée.")
        except Exception as e:
            logger.error(f"Erreur lors de la migration JSON vers SQLite: {e}", exc_info=True)

    def _ensure_user_row(self, user_id: str):
        cursor = self._conn.cursor()
        cursor.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return
        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO user_preferences (user_id, preferences_json, created_at, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, json.dumps({}, ensure_ascii=False), now, now)
        )
        self._conn.commit()

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Récupère les préférences d'un utilisateur"""
        self._ensure_user_row(user_id)
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT preferences_json FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["preferences_json"] or "{}")
        except json.JSONDecodeError:
            return {}

    def save_user_preference(self, user_id: str, key: str, value: Any):
        """Sauvegarde une préférence utilisateur"""
        prefs = self.get_user_preferences(user_id)
        prefs[key] = value
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE user_preferences
            SET preferences_json = ?, last_updated = ?
            WHERE user_id = ?
            """,
            (json.dumps(prefs, ensure_ascii=False), now, user_id)
        )
        self._conn.commit()

    def add_conversation(self, user_id: str, question: str, response: str):
        """Ajoute une conversation à l'historique"""
        self._ensure_user_row(user_id)
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_conversations (user_id, question, response, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, question, response, datetime.now().isoformat())
        )
        cursor.execute(
            "UPDATE user_preferences SET last_updated = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id)
        )
        self._conn.commit()

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Récupère l'historique des conversations"""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT question, response, timestamp
            FROM user_conversations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        results = [
            {
                "question": row["question"],
                "response": row["response"],
                "timestamp": row["timestamp"]
            }
            for row in rows
        ]
        return list(reversed(results))


# Instance globale de la mémoire
_user_memory = UserMemory()
