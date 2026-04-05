"""
Symposium — API test suite.

Requires the server to be running: uvicorn main:app --port 8765
Run with: pytest tests/ -v
"""

import os
import pytest
import requests
import time

BASE = "http://127.0.0.1:8765"
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def server():
    """Verify server is up before running tests."""
    try:
        r = requests.get(f"{BASE}/", timeout=3)
        r.raise_for_status()
    except Exception:
        pytest.skip("Server not running — start with: uvicorn main:app --port 8765")


@pytest.fixture(scope="session")
def panel_ids(server):
    """Pick a fast 3-figure panel for chat tests."""
    return ["socrates", "nietzsche", "feynman"]


@pytest.fixture(scope="session")
def chat_session(server, panel_ids):
    """Start a single chat session shared across turn tests."""
    r = requests.post(f"{BASE}/chat/start", json={
        "question": "Is courage a virtue or a personality trait?",
        "figure_ids": panel_ids,
        "max_turns": 3
    })
    assert r.status_code == 200, r.text
    return r.json()


# ─── BYOK (Bring Your Own Key) tests ─────────────────────────────────────────

@pytest.mark.skip(reason="Pending Task 4: main.py BYOK wiring not yet complete")
def test_ask_requires_api_key(server):
    """Missing X-API-Key header → should return 401 once BYOK is wired."""
    r = requests.post(f"{BASE}/chat/start", json={
        "question": "What is truth?",
        "figure_ids": ["socrates"],
        "max_turns": 1
    })
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


def test_ask_with_api_key_succeeds(server):
    """Valid X-API-Key → 200 with compliance disclaimer present."""
    if not API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")
    r = requests.post(
        f"{BASE}/chat/start",
        headers={"X-API-Key": API_KEY},
        json={
            "question": "What is truth?",
            "figure_ids": ["socrates"],
            "max_turns": 1
        }
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "compliance" in body
    assert "disclaimer" in body["compliance"]


# ─── Server ─────────────────────────────────────────────────────────────────

class TestServer:
    def test_root(self, server):
        r = requests.get(f"{BASE}/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Symposium"
        assert "POST /chat/start" in data["endpoints"]


# ─── Figures ────────────────────────────────────────────────────────────────

class TestFigures:
    def test_list_figures(self, server):
        r = requests.get(f"{BASE}/figures")
        assert r.status_code == 200
        figures = r.json()["figures"]
        assert len(figures) >= 5
        ids = [f["id"] for f in figures]
        assert "socrates" in ids
        assert "nietzsche" in ids

    def test_figure_has_required_fields(self, server):
        r = requests.get(f"{BASE}/figures")
        for fig in r.json()["figures"]:
            assert "id" in fig
            assert "name" in fig
            assert "role" in fig
            assert "soul_signature" in fig

    def test_figure_detail(self, server):
        r = requests.get(f"{BASE}/figures/socrates")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "socrates"
        assert "system_prompt" not in data  # must not be exposed

    def test_figure_not_found(self, server):
        r = requests.get(f"{BASE}/figures/voltaire")
        assert r.status_code == 404


# ─── Panel suggestion ───────────────────────────────────────────────────────

class TestPanelSuggest:
    def test_suggest_returns_panel(self, server):
        r = requests.post(f"{BASE}/panel/suggest", json={
            "question": "What is the nature of reality?",
            "size": 3
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["panel"]) == 3
        assert "tensions" in data

    def test_suggest_empty_question(self, server):
        r = requests.post(f"{BASE}/panel/suggest", json={"question": "  "})
        assert r.status_code == 400


# ─── Chat: start ────────────────────────────────────────────────────────────

class TestChatStart:
    def test_opening_round(self, chat_session, panel_ids):
        data = chat_session
        assert "session_id" in data
        assert data["turn"] == 0
        assert data["is_complete"] is False
        # All 3 figures should respond in opening
        speaker_ids = [m["speaker_id"] for m in data["messages"]]
        for fid in panel_ids:
            assert fid in speaker_ids, f"{fid} missing from opening round"

    def test_opening_messages_not_empty(self, chat_session):
        for msg in chat_session["messages"]:
            assert len(msg["content"].strip()) > 20

    def test_opening_has_role_labels(self, chat_session):
        for msg in chat_session["messages"]:
            assert msg["role"] is not None

    def test_token_usage_tracked(self, chat_session):
        usage = chat_session["token_usage"]
        assert usage["input_tokens"] > 0
        assert usage["output_tokens"] > 0

    def test_turns_remaining(self, chat_session):
        # max_turns=3, turn=0, so 3 remaining
        assert chat_session["turns_remaining"] == 3

    def test_empty_question_rejected(self, server):
        r = requests.post(f"{BASE}/chat/start", json={"question": "  "})
        assert r.status_code == 400

    def test_unknown_figure_rejected(self, server):
        r = requests.post(f"{BASE}/chat/start", json={
            "question": "What is truth?",
            "figure_ids": ["socrates", "does_not_exist"]
        })
        assert r.status_code == 400


# ─── Chat: turns ────────────────────────────────────────────────────────────

class TestChatTurns:
    def test_reply_turn(self, chat_session):
        sid = chat_session["session_id"]
        r = requests.post(f"{BASE}/chat/{sid}", json={
            "message": "But aren't courage and virtue both learned behaviours?"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["turn"] == 1
        # 1-2 figures should reply (not all 3)
        figure_msgs = [m for m in data["messages"] if m["speaker_id"] != "user"]
        assert 1 <= len(figure_msgs) <= 2

    def test_user_message_echoed(self, chat_session):
        sid = chat_session["session_id"]
        r = requests.post(f"{BASE}/chat/{sid}", json={
            "message": "What separates the brave from the reckless?"
        })
        assert r.status_code == 200
        data = r.json()
        user_msgs = [m for m in data["messages"] if m["speaker_id"] == "user"]
        assert len(user_msgs) == 1
        assert "brave" in user_msgs[0]["content"].lower() or "reckless" in user_msgs[0]["content"].lower()

    def test_closing_round_fires(self, chat_session):
        """Final turn should trigger closing statements from all figures."""
        sid = chat_session["session_id"]
        # Send last message (turn 3 of max_turns=3)
        r = requests.post(f"{BASE}/chat/{sid}", json={
            "message": "Last question: is there courage without fear?"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_complete"] is True
        closing_msgs = [m for m in data["messages"] if m["is_closing"]]
        # All figures should have a closing statement
        closing_speakers = {m["speaker_id"] for m in closing_msgs}
        assert len(closing_speakers) >= 2

    def test_session_complete_rejects_new_message(self, chat_session):
        sid = chat_session["session_id"]
        r = requests.post(f"{BASE}/chat/{sid}", json={"message": "one more thing"})
        assert r.status_code == 400


# ─── Chat: retrieval ────────────────────────────────────────────────────────

class TestChatRetrieval:
    def test_get_session(self, chat_session):
        sid = chat_session["session_id"]
        r = requests.get(f"{BASE}/chat/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == sid
        assert data["status"] == "complete"
        assert len(data["messages"]) > 0

    def test_get_session_not_found(self, server):
        r = requests.get(f"{BASE}/chat/doesnotexist")
        assert r.status_code == 404

    def test_list_chats(self, chat_session, server):
        r = requests.get(f"{BASE}/chats")
        assert r.status_code == 200
        sessions = r.json()["sessions"]
        ids = [s["id"] for s in sessions]
        assert chat_session["session_id"] in ids

    def test_session_has_token_totals(self, chat_session):
        sid = chat_session["session_id"]
        r = requests.get(f"{BASE}/chat/{sid}")
        usage = r.json()["token_usage"]
        assert usage["input_tokens"] > 1000   # realistic lower bound
        assert usage["output_tokens"] > 200
