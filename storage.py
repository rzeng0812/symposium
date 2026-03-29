"""
SQLite storage for Symposium sessions, responses, and quality scores.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "symposium.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                question    TEXT NOT NULL,
                panel_ids    TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS responses (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT NOT NULL,
                figure_id            TEXT NOT NULL,
                figure_name          TEXT NOT NULL,
                role            TEXT NOT NULL,
                response_text        TEXT NOT NULL,
                score_in_character   INTEGER,
                score_depth          INTEGER,
                score_soul_alignment INTEGER,
                score_notes          TEXT,
                compliance_status    TEXT,
                compliance_risk_level INTEGER,
                compliance_flags     TEXT,
                compliance_reason    TEXT,
                created_at           TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                figure_id   TEXT NOT NULL,
                rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                note        TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id                  TEXT PRIMARY KEY,
                question            TEXT NOT NULL,
                panel_ids            TEXT NOT NULL,
                max_turns           INTEGER NOT NULL DEFAULT 10,
                turns_used          INTEGER NOT NULL DEFAULT 0,
                total_input_tokens  INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                status              TEXT NOT NULL DEFAULT 'active',
                created_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                turn         INTEGER NOT NULL,
                speaker_id   TEXT NOT NULL,
                speaker_name TEXT NOT NULL,
                role    TEXT,
                content      TEXT NOT NULL,
                is_closing   INTEGER NOT NULL DEFAULT 0,
                input_tokens  INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
            );
        """)


def save_session(question: str, panel_ids: list[str]) -> str:
    session_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, question, panel_ids) VALUES (?, ?, ?)",
            (session_id, question, json.dumps(panel_ids))
        )
    return session_id


def save_response(session_id: str, figure_id: str, figure_name: str,
                  role: str, response_text: str) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO responses
               (session_id, figure_id, figure_name, role, response_text)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, figure_id, figure_name, role, response_text)
        )
        return cursor.lastrowid


def save_quality_scores(response_id: int, in_character: int,
                        depth: int, soul_alignment: int, notes: str):
    with get_conn() as conn:
        conn.execute(
            """UPDATE responses SET
               score_in_character=?, score_depth=?, score_soul_alignment=?, score_notes=?
               WHERE id=?""",
            (in_character, depth, soul_alignment, notes, response_id)
        )


def save_rating(session_id: str, figure_id: str, rating: int, note: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ratings (session_id, figure_id, rating, note) VALUES (?, ?, ?, ?)",
            (session_id, figure_id, rating, note)
        )


def get_session(session_id: str) -> dict | None:
    with get_conn() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not session:
            return None

        responses = conn.execute(
            "SELECT * FROM responses WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()

        ratings = conn.execute(
            "SELECT * FROM ratings WHERE session_id=?", (session_id,)
        ).fetchall()

        return {
            "id": session["id"],
            "question": session["question"],
            "panel_ids": json.loads(session["panel_ids"]),
            "created_at": session["created_at"],
            "responses": [dict(r) for r in responses],
            "ratings": [dict(r) for r in ratings]
        }


def get_history(limit: int = 20, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        sessions = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()

        result = []
        for s in sessions:
            responses = conn.execute(
                """SELECT figure_id, figure_name, role,
                   score_in_character, score_depth, score_soul_alignment
                   FROM responses WHERE session_id=? ORDER BY id""",
                (s["id"],)
            ).fetchall()
            result.append({
                "id": s["id"],
                "question": s["question"],
                "panel_ids": json.loads(s["panel_ids"]),
                "created_at": s["created_at"],
                "responses": [dict(r) for r in responses]
            })
        return result


def get_quality_stats() -> list[dict]:
    """Aggregate quality scores and ratings per figure."""
    with get_conn() as conn:
        stats = conn.execute("""
            SELECT
                r.figure_id,
                r.figure_name,
                COUNT(*) as total_responses,
                ROUND(AVG(r.score_in_character), 1) as avg_in_character,
                ROUND(AVG(r.score_depth), 1) as avg_depth,
                ROUND(AVG(r.score_soul_alignment), 1) as avg_soul_alignment,
                ROUND(AVG(r.score_in_character + r.score_depth + r.score_soul_alignment) / 3.0, 1) as avg_overall,
                COUNT(rt.id) as total_ratings,
                ROUND(AVG(rt.rating), 2) as avg_user_rating
            FROM responses r
            LEFT JOIN ratings rt ON rt.session_id = r.session_id AND rt.figure_id = r.figure_id
            WHERE r.score_in_character IS NOT NULL
            GROUP BY r.figure_id
            ORDER BY avg_overall DESC
        """).fetchall()
        return [dict(s) for s in stats]


# ─── Chat storage ────────────────────────────────────────────────────────────

def save_chat_session(question: str, panel_ids: list[str], max_turns: int) -> str:
    session_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO chat_sessions (id, question, panel_ids, max_turns)
               VALUES (?, ?, ?, ?)""",
            (session_id, question, json.dumps(panel_ids), max_turns)
        )
    return session_id


def save_chat_message(session_id: str, turn: int, speaker_id: str,
                      speaker_name: str, role: str | None,
                      content: str, is_closing: bool = False,
                      input_tokens: int = 0, output_tokens: int = 0) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO chat_messages
               (session_id, turn, speaker_id, speaker_name, role,
                content, is_closing, input_tokens, output_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, turn, speaker_id, speaker_name, role,
             content, int(is_closing), input_tokens, output_tokens)
        )
        return cursor.lastrowid


def update_chat_turn(session_id: str, turns_used: int,
                     added_input: int, added_output: int, status: str = "active"):
    with get_conn() as conn:
        conn.execute(
            """UPDATE chat_sessions SET
               turns_used=?,
               total_input_tokens=total_input_tokens+?,
               total_output_tokens=total_output_tokens+?,
               status=?
               WHERE id=?""",
            (turns_used, added_input, added_output, status, session_id)
        )


def get_chat_history(limit: int = 20, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        sessions = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        result = []
        for s in sessions:
            # First and last non-user message for preview
            preview = conn.execute(
                """SELECT speaker_name, content FROM chat_messages
                   WHERE session_id=? AND speaker_id != 'user' AND is_closing=0
                   ORDER BY id LIMIT 1""",
                (s["id"],)
            ).fetchone()
            result.append({
                "id": s["id"],
                "question": s["question"],
                "panel_ids": json.loads(s["panel_ids"]),
                "max_turns": s["max_turns"],
                "turns_used": s["turns_used"],
                "status": s["status"],
                "token_usage": {
                    "input_tokens": s["total_input_tokens"],
                    "output_tokens": s["total_output_tokens"]
                },
                "created_at": s["created_at"],
                "preview": dict(preview) if preview else None
            })
        return result


def get_chat_session(session_id: str) -> dict | None:
    with get_conn() as conn:
        session = conn.execute(
            "SELECT * FROM chat_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not session:
            return None

        messages = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()

        return {
            "id": session["id"],
            "question": session["question"],
            "panel_ids": json.loads(session["panel_ids"]),
            "max_turns": session["max_turns"],
            "turns_used": session["turns_used"],
            "status": session["status"],
            "token_usage": {
                "input_tokens": session["total_input_tokens"],
                "output_tokens": session["total_output_tokens"]
            },
            "created_at": session["created_at"],
            "messages": [dict(m) for m in messages]
        }
