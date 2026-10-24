"""Small thread-safe SQLite persistence layer for quiz leaderboards."""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "data/quizbot.sqlite3")
_lock = threading.RLock()

def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db() -> None:
    with _lock, connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                answered INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(chat_id, user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_chat ON scores(chat_id, points DESC)")
        conn.commit()

def save_session_scores(chat_id: int, scores: dict[int, dict]) -> None:
    if not scores:
        return
    with _lock, connect() as conn:
        for user_id, item in scores.items():
            conn.execute("""
                INSERT INTO scores(chat_id,user_id,name,points,correct,answered,updated_at)
                VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id,user_id) DO UPDATE SET
                    name=excluded.name,
                    points=scores.points+excluded.points,
                    correct=scores.correct+excluded.correct,
                    answered=scores.answered+excluded.answered,
                    updated_at=CURRENT_TIMESTAMP
            """, (chat_id, user_id, item["name"], item["points"], item["correct"], item["answered"]))
        conn.commit()

def leaderboard(chat_id: int, limit: int = 10) -> list[dict]:
    with _lock, connect() as conn:
        rows = conn.execute("""
            SELECT user_id,name,points,correct,answered FROM scores
            WHERE chat_id=? ORDER BY points DESC, correct DESC, answered ASC LIMIT ?
        """, (chat_id, limit)).fetchall()
        return [dict(row) for row in rows]

def reset_chat(chat_id: int) -> None:
    with _lock, connect() as conn:
        conn.execute("DELETE FROM scores WHERE chat_id=?", (chat_id,))
        conn.commit()
