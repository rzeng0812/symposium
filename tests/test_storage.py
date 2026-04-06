"""
Unit tests — storage module.

Uses a temporary SQLite database so tests never touch symposium.db.
"""

import json
import pytest
import storage


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a temp file for each test."""
    temp_db = tmp_path / "test.db"
    monkeypatch.setattr(storage, "DB_PATH", temp_db)
    storage.init_db()
    yield


# ─── init_db ─────────────────────────────────────────────────────────────────

def test_init_db_creates_tables():
    conn = storage.get_conn()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {"sessions", "responses", "ratings", "chat_sessions", "chat_messages"}
    assert expected.issubset(tables)
    conn.close()


def test_init_db_is_idempotent():
    """Calling init_db twice should not raise."""
    storage.init_db()
    storage.init_db()


# ─── sessions ────────────────────────────────────────────────────────────────

def test_save_session_returns_id():
    sid = storage.save_session("What is truth?", ["socrates", "nietzsche"])
    assert isinstance(sid, str) and len(sid) > 0


def test_save_session_id_is_unique():
    sid1 = storage.save_session("Q1", ["socrates"])
    sid2 = storage.save_session("Q2", ["nietzsche"])
    assert sid1 != sid2


def test_get_session_returns_saved_data():
    sid = storage.save_session("What is truth?", ["socrates", "nietzsche"])
    session = storage.get_session(sid)
    assert session is not None
    assert session["id"] == sid
    assert session["question"] == "What is truth?"
    assert session["panel_ids"] == ["socrates", "nietzsche"]


def test_get_session_unknown_returns_none():
    assert storage.get_session("doesnotexist") is None


def test_get_history_returns_sessions():
    storage.save_session("Q1", ["socrates"])
    storage.save_session("Q2", ["nietzsche"])
    history = storage.get_history()
    assert len(history) == 2


def test_get_history_limit():
    for i in range(5):
        storage.save_session(f"Q{i}", ["socrates"])
    history = storage.get_history(limit=3)
    assert len(history) == 3


def test_get_history_offset():
    for i in range(5):
        storage.save_session(f"Q{i}", ["socrates"])
    all_history = storage.get_history(limit=10)
    offset_history = storage.get_history(limit=10, offset=2)
    assert len(offset_history) == 3


# ─── responses ───────────────────────────────────────────────────────────────

def test_save_response_returns_id():
    sid = storage.save_session("Q", ["socrates"])
    rid = storage.save_response(sid, "socrates", "Socrates", "The Destabilizer", "Some text.")
    assert isinstance(rid, int)


def test_save_response_appears_in_session():
    sid = storage.save_session("Q", ["socrates"])
    storage.save_response(sid, "socrates", "Socrates", "The Destabilizer", "Some text.")
    session = storage.get_session(sid)
    assert len(session["responses"]) == 1
    r = session["responses"][0]
    assert r["figure_id"] == "socrates"
    assert r["response_text"] == "Some text."


def test_save_quality_scores_updates_response():
    sid = storage.save_session("Q", ["socrates"])
    rid = storage.save_response(sid, "socrates", "Socrates", "The Destabilizer", "Some text.")
    storage.save_quality_scores(rid, in_character=8, depth=7, soul_alignment=9,
                                notes="Strong performance.")
    session = storage.get_session(sid)
    r = session["responses"][0]
    assert r["score_in_character"] == 8
    assert r["score_depth"] == 7
    assert r["score_soul_alignment"] == 9
    assert r["score_notes"] == "Strong performance."


# ─── ratings ─────────────────────────────────────────────────────────────────

def test_save_rating_appears_in_session():
    sid = storage.save_session("Q", ["socrates"])
    storage.save_rating(sid, "socrates", 4, "Very in-character.")
    session = storage.get_session(sid)
    assert len(session["ratings"]) == 1
    assert session["ratings"][0]["rating"] == 4
    assert session["ratings"][0]["note"] == "Very in-character."


def test_save_rating_without_note():
    sid = storage.save_session("Q", ["socrates"])
    storage.save_rating(sid, "socrates", 5)
    session = storage.get_session(sid)
    assert session["ratings"][0]["rating"] == 5


# ─── chat sessions ───────────────────────────────────────────────────────────

def test_save_chat_session_returns_id():
    sid = storage.save_chat_session("Does free will exist?", ["socrates", "nietzsche"], max_turns=5)
    assert isinstance(sid, str) and len(sid) > 0


def test_get_chat_session_returns_saved():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=3)
    session = storage.get_chat_session(sid)
    assert session is not None
    assert session["id"] == sid
    assert session["question"] == "Q"
    assert session["panel_ids"] == ["socrates"]
    assert session["max_turns"] == 3
    assert session["status"] == "active"


def test_get_chat_session_unknown_returns_none():
    assert storage.get_chat_session("doesnotexist") is None


def test_save_chat_message_appears_in_session():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=3)
    storage.save_chat_message(sid, turn=0, speaker_id="socrates",
                              speaker_name="Socrates", role="The Destabilizer",
                              content="But what do you mean by free?",
                              is_closing=False, input_tokens=100, output_tokens=50)
    session = storage.get_chat_session(sid)
    assert len(session["messages"]) == 1
    msg = session["messages"][0]
    assert msg["speaker_id"] == "socrates"
    assert msg["content"] == "But what do you mean by free?"
    assert msg["is_closing"] == 0


def test_save_chat_message_closing_flag():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=3)
    storage.save_chat_message(sid, turn=2, speaker_id="socrates",
                              speaker_name="Socrates", role="The Destabilizer",
                              content="My closing thought.", is_closing=True)
    session = storage.get_chat_session(sid)
    assert session["messages"][0]["is_closing"] == 1


def test_update_chat_turn_increments_tokens():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=5)
    storage.update_chat_turn(sid, turns_used=1, added_input=200, added_output=100)
    storage.update_chat_turn(sid, turns_used=2, added_input=300, added_output=150)
    session = storage.get_chat_session(sid)
    assert session["turns_used"] == 2
    assert session["token_usage"]["input_tokens"] == 500
    assert session["token_usage"]["output_tokens"] == 250


def test_update_chat_turn_status():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=1)
    storage.update_chat_turn(sid, turns_used=1, added_input=100, added_output=50,
                             status="complete")
    session = storage.get_chat_session(sid)
    assert session["status"] == "complete"


def test_get_chat_history_returns_sessions():
    storage.save_chat_session("Q1", ["socrates"], max_turns=3)
    storage.save_chat_session("Q2", ["nietzsche"], max_turns=5)
    history = storage.get_chat_history()
    assert len(history) == 2


def test_chat_session_token_usage_starts_at_zero():
    sid = storage.save_chat_session("Q", ["socrates"], max_turns=3)
    session = storage.get_chat_session(sid)
    assert session["token_usage"]["input_tokens"] == 0
    assert session["token_usage"]["output_tokens"] == 0


# ─── quality stats ───────────────────────────────────────────────────────────

def test_get_quality_stats_empty():
    stats = storage.get_quality_stats()
    assert stats == []


def test_get_quality_stats_with_scores():
    sid = storage.save_session("Q", ["socrates"])
    rid = storage.save_response(sid, "socrates", "Socrates", "The Destabilizer", "Some text.")
    storage.save_quality_scores(rid, 8, 7, 9, "Good.")
    stats = storage.get_quality_stats()
    assert len(stats) == 1
    assert stats[0]["figure_id"] == "socrates"
    assert stats[0]["avg_in_character"] == 8.0
