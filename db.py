"""SQLite persistence for scores and each user's saved quiz library."""
from __future__ import annotations

import json
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
                chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
                answered INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(chat_id, user_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_chat ON scores(chat_id, points DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_quizzes_owner ON saved_quizzes(owner_id, id DESC)")
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
                    name=excluded.name, points=scores.points+excluded.points,
                    correct=scores.correct+excluded.correct, answered=scores.answered+excluded.answered,
                    updated_at=CURRENT_TIMESTAMP
            """, (chat_id, user_id, item["name"], item["points"], item["correct"], item["answered"]))
        conn.commit()


def leaderboard(chat_id: int, limit: int = 10) -> list[dict]:
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT user_id,name,points,correct,answered FROM scores WHERE chat_id=? "
            "ORDER BY points DESC, correct DESC, answered ASC LIMIT ?", (chat_id, limit)
        ).fetchall()
        return [dict(row) for row in rows]


def reset_chat(chat_id: int) -> None:
    with _lock, connect() as conn:
        conn.execute("DELETE FROM scores WHERE chat_id=?", (chat_id,))
        conn.commit()


def save_quiz(owner_id: int, title: str, source: str, questions: list[dict]) -> int:
    with _lock, connect() as conn:
        cur = conn.execute(
            "INSERT INTO saved_quizzes(owner_id,title,source,questions_json) VALUES(?,?,?,?)",
            (owner_id, title[:120], source[:14000], json.dumps(questions, ensure_ascii=False))
        )
        conn.commit()
        return int(cur.lastrowid)


def get_quiz(quiz_id: int, owner_id: int | None = None) -> dict | None:
    with _lock, connect() as conn:
        if owner_id is None:
            row = conn.execute("SELECT * FROM saved_quizzes WHERE id=?", (quiz_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM saved_quizzes WHERE id=? AND owner_id=?", (quiz_id, owner_id)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["questions"] = json.loads(result.pop("questions_json"))
        return result


def list_quizzes(owner_id: int, limit: int = 20) -> list[dict]:
    with _lock, connect() as conn:
        rows = conn.execute(
            "SELECT id,title,created_at FROM saved_quizzes WHERE owner_id=? ORDER BY id DESC LIMIT ?",
            (owner_id, limit)
        ).fetchall()
        return [dict(row) for row in rows]
