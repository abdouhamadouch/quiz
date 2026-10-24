"""Persistent storage for quiz libraries, drafts, scores, and quiz settings.

SQLite is the zero-configuration default. Set DATABASE_URL to a PostgreSQL URL
for durable hosted storage; SQLite durability depends on the host's disk policy.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DATABASE_PATH", "data/quizbot.sqlite3")
_USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
_lock = threading.RLock()


def _sql(statement: str) -> str:
    return statement.replace("?", "%s") if _USE_POSTGRES else statement


def connect():
    if _USE_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL requires psycopg[binary] in requirements.txt") from exc
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _rows(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def init_db() -> None:
    with _lock, connect() as conn:
        if _USE_POSTGRES:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    chat_id BIGINT NOT NULL, user_id BIGINT NOT NULL, name TEXT NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
                    answered INTEGER NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(chat_id, user_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_chat ON scores(chat_id, points DESC)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_quizzes (
                    id BIGSERIAL PRIMARY KEY, owner_id BIGINT NOT NULL, title TEXT NOT NULL,
                    source TEXT NOT NULL, questions_json TEXT NOT NULL,
                    seconds INTEGER NOT NULL DEFAULT 20, mode TEXT NOT NULL DEFAULT 'exam',
                    difficulty TEXT NOT NULL DEFAULT 'medium', question_count INTEGER NOT NULL DEFAULT 5,
                    category TEXT NOT NULL DEFAULT 'عام', created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS group_drafts (
                    chat_id BIGINT PRIMARY KEY, owner_id BIGINT NOT NULL, quiz_id BIGINT NOT NULL,
                    quiz_json TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL,
                    title TEXT NOT NULL, source TEXT NOT NULL, questions_json TEXT NOT NULL,
                    seconds INTEGER NOT NULL DEFAULT 20, mode TEXT NOT NULL DEFAULT 'exam',
                    difficulty TEXT NOT NULL DEFAULT 'medium', question_count INTEGER NOT NULL DEFAULT 5,
                    category TEXT NOT NULL DEFAULT 'عام', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS group_drafts (
                    chat_id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, quiz_id INTEGER NOT NULL,
                    quiz_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
        # Upgrade databases created by earlier versions without losing saved quizzes.
        if _USE_POSTGRES:
            for column, definition in (
                ("seconds", "INTEGER NOT NULL DEFAULT 20"),
                ("mode", "TEXT NOT NULL DEFAULT 'exam'"),
                ("difficulty", "TEXT NOT NULL DEFAULT 'medium'"),
                ("question_count", "INTEGER NOT NULL DEFAULT 5"),
                ("category", "TEXT NOT NULL DEFAULT 'عام'"),
            ):
                conn.execute(f"ALTER TABLE saved_quizzes ADD COLUMN IF NOT EXISTS {column} {definition}")
        else:
            for column, definition in (
                ("seconds", "INTEGER NOT NULL DEFAULT 20"),
                ("mode", "TEXT NOT NULL DEFAULT 'exam'"),
                ("difficulty", "TEXT NOT NULL DEFAULT 'medium'"),
                ("question_count", "INTEGER NOT NULL DEFAULT 5"),
                ("category", "TEXT NOT NULL DEFAULT 'عام'"),
            ):
                try:
                    conn.execute(f"ALTER TABLE saved_quizzes ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
        result_timestamp_type = "TIMESTAMPTZ" if _USE_POSTGRES else "TEXT"
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS quiz_results (
                chat_id BIGINT NOT NULL, quiz_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
                name TEXT NOT NULL, points INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
                answered INTEGER NOT NULL DEFAULT 0, created_at {result_timestamp_type} NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(chat_id, quiz_id, user_id)
            )
        """)
        if _USE_POSTGRES:
            # Upgrade the earlier text timestamp schema without discarding stored results.
            conn.execute("ALTER TABLE quiz_results ALTER COLUMN created_at DROP DEFAULT")
            conn.execute("ALTER TABLE quiz_results ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at::timestamptz")
            conn.execute("ALTER TABLE quiz_results ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_results_chat_quiz ON quiz_results(chat_id, quiz_id, points DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_quizzes_owner ON saved_quizzes(owner_id, id DESC)")
        conn.commit()


def save_session_scores(chat_id: int, scores: dict[int, dict]) -> None:
    if not scores:
        return
    with _lock, connect() as conn:
        for user_id, item in scores.items():
            conn.execute(_sql("""
                INSERT INTO scores(chat_id,user_id,name,points,correct,answered,updated_at)
                VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id,user_id) DO UPDATE SET
                    name=excluded.name, points=scores.points+excluded.points,
                    correct=scores.correct+excluded.correct, answered=scores.answered+excluded.answered,
                    updated_at=CURRENT_TIMESTAMP
            """), (chat_id, user_id, item["name"], item["points"], item["correct"], item["answered"]))
        conn.commit()


def leaderboard(chat_id: int, limit: int = 10) -> list[dict]:
    with _lock, connect() as conn:
        return _rows(conn.execute(_sql(
            "SELECT user_id,name,points,correct,answered FROM scores WHERE chat_id=? "
            "ORDER BY points DESC, correct DESC, answered ASC LIMIT ?"
        ), (chat_id, limit)))


def reset_chat(chat_id: int) -> None:
    with _lock, connect() as conn:
        conn.execute(_sql("DELETE FROM scores WHERE chat_id=?"), (chat_id,))
        conn.commit()


def save_quiz(owner_id: int, title: str, source: str, questions: list[dict],
              seconds: int = 20, mode: str = "exam", difficulty: str = "medium", category: str = "عام") -> int:
    with _lock, connect() as conn:
        cur = conn.execute(_sql(
            "INSERT INTO saved_quizzes(owner_id,title,source,questions_json,seconds,mode,difficulty,question_count,category) "
            "VALUES(?,?,?,?,?,?,?,?,?) RETURNING id"
        ), (owner_id, title[:120], source[:14000], json.dumps(questions, ensure_ascii=False),
            max(10, min(60, int(seconds))), mode if mode in {"exam", "review_manual", "review_all"} else "exam",
            difficulty if difficulty in {"easy", "medium", "hard"} else "medium", len(questions), category.strip()[:80] or "عام"))
        row = cur.fetchone()
        conn.commit()
        return int(row["id"] if isinstance(row, dict) else row[0])


def get_quiz(quiz_id: int, owner_id: int | None = None) -> dict | None:
    with _lock, connect() as conn:
        if owner_id is None:
            row = conn.execute(_sql("SELECT * FROM saved_quizzes WHERE id=?"), (quiz_id,)).fetchone()
        else:
            row = conn.execute(_sql("SELECT * FROM saved_quizzes WHERE id=? AND owner_id=?"), (quiz_id, owner_id)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["questions"] = json.loads(result.pop("questions_json"))
        return result


def list_quizzes(owner_id: int, limit: int = 20, search: str = "") -> list[dict]:
    with _lock, connect() as conn:
        if search.strip():
            pattern = f"%{search.strip()[:100]}%"
            cursor = conn.execute(_sql(
                "SELECT id,title,created_at,question_count,category,seconds,mode FROM saved_quizzes "
                "WHERE owner_id=? AND (title LIKE ? OR source LIKE ? OR category LIKE ?) ORDER BY id DESC LIMIT ?"
            ), (owner_id, pattern, pattern, pattern, limit))
        else:
            cursor = conn.execute(_sql(
                "SELECT id,title,created_at,question_count,category,seconds,mode FROM saved_quizzes "
                "WHERE owner_id=? ORDER BY id DESC LIMIT ?"
            ), (owner_id, limit))
        return _rows(cursor)


def delete_quiz(quiz_id: int, owner_id: int) -> bool:
    with _lock, connect() as conn:
        cur = conn.execute(_sql("DELETE FROM saved_quizzes WHERE id=? AND owner_id=?"), (quiz_id, owner_id))
        conn.commit()
        return cur.rowcount > 0


def rename_quiz(quiz_id: int, owner_id: int, title: str) -> bool:
    with _lock, connect() as conn:
        cur = conn.execute(_sql("UPDATE saved_quizzes SET title=? WHERE id=? AND owner_id=?"),
                           (title.strip()[:120], quiz_id, owner_id))
        conn.commit()
        return cur.rowcount > 0


def update_quiz_questions(quiz_id: int, owner_id: int, questions: list[dict]) -> bool:
    with _lock, connect() as conn:
        cur = conn.execute(_sql(
            "UPDATE saved_quizzes SET questions_json=?,question_count=? WHERE id=? AND owner_id=?"
        ), (json.dumps(questions, ensure_ascii=False), len(questions), quiz_id, owner_id))
        conn.commit()
        return cur.rowcount > 0


def copy_quiz(quiz_id: int, owner_id: int) -> int | None:
    saved = get_quiz(quiz_id, owner_id)
    if not saved:
        return None
    return save_quiz(owner_id, f"{saved['title']} (نسخة)", saved["source"], saved["questions"],
                     saved.get("seconds", 20), saved.get("mode", "exam"), saved.get("difficulty", "medium"), saved.get("category", "عام"))


def save_group_draft(chat_id: int, owner_id: int, quiz: dict) -> None:
    payload = json.dumps(quiz, ensure_ascii=False, default=str)
    with _lock, connect() as conn:
        conn.execute(_sql("""
            INSERT INTO group_drafts(chat_id,owner_id,quiz_id,quiz_json,updated_at)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET owner_id=excluded.owner_id,
                quiz_id=excluded.quiz_id,quiz_json=excluded.quiz_json,updated_at=CURRENT_TIMESTAMP
        """), (chat_id, owner_id, int(quiz["id"]), payload))
        conn.commit()


def get_group_drafts() -> dict[int, dict]:
    with _lock, connect() as conn:
        rows = _rows(conn.execute("SELECT chat_id,owner_id,quiz_json FROM group_drafts"))
    result = {}
    for row in rows:
        try:
            result[int(row["chat_id"])] = {"owner_id": int(row["owner_id"]), "quiz": json.loads(row["quiz_json"])}
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return result


def delete_group_draft(chat_id: int) -> None:
    with _lock, connect() as conn:
        conn.execute(_sql("DELETE FROM group_drafts WHERE chat_id=?"), (chat_id,))
        conn.commit()



def save_quiz_results(chat_id: int, quiz_id: int, scores: dict[int, dict]) -> None:
    if not scores:
        return
    with _lock, connect() as conn:
        for user_id, item in scores.items():
            conn.execute(_sql("""
                INSERT INTO quiz_results(chat_id,quiz_id,user_id,name,points,correct,answered,created_at)
                VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id,quiz_id,user_id) DO UPDATE SET
                    name=excluded.name, points=excluded.points, correct=excluded.correct,
                    answered=excluded.answered, created_at=CURRENT_TIMESTAMP
            """), (chat_id, quiz_id, user_id, item["name"], item["points"], item["correct"], item["answered"]))
        conn.commit()


def quiz_leaderboard(chat_id: int, quiz_id: int, limit: int = 10) -> list[dict]:
    with _lock, connect() as conn:
        return _rows(conn.execute(_sql(
            "SELECT user_id,name,points,correct,answered FROM quiz_results "
            "WHERE chat_id=? AND quiz_id=? ORDER BY points DESC,correct DESC,answered ASC LIMIT ?"
        ), (chat_id, quiz_id, limit)))



def set_quiz_category(quiz_id: int, owner_id: int, category: str) -> bool:
    with _lock, connect() as conn:
        cur = conn.execute(_sql("UPDATE saved_quizzes SET category=? WHERE id=? AND owner_id=?"),
                           (category.strip()[:80] or "عام", quiz_id, owner_id))
        conn.commit()
        return cur.rowcount > 0


def user_stats(user_id: int) -> dict:
    with _lock, connect() as conn:
        score = conn.execute(_sql(
            "SELECT COALESCE(SUM(points),0) AS points,COALESCE(SUM(correct),0) AS correct,"
            "COALESCE(SUM(answered),0) AS answered,COUNT(*) AS groups_count FROM scores "
            "WHERE user_id=? AND chat_id<0"
        ), (user_id,)).fetchone()
        quizzes = conn.execute(_sql("SELECT COUNT(*) AS quiz_count FROM saved_quizzes WHERE owner_id=?"),
                               (user_id,)).fetchone()
        return {"points": int(score["points"]), "correct": int(score["correct"]),
                "answered": int(score["answered"]), "groups_count": int(score["groups_count"]),
                "quiz_count": int(quizzes["quiz_count"])}
