"""
No-network endpoint tests.

Mocks anthropic.Anthropic globally and drives the real FastAPI app
in-process via TestClient — exercises actual routing, Principle 7 review,
the refusal-swap, and DB persistence with zero network calls and no API
credits required. Complements test_api.py, which needs a live server and
a real (paid) key; these run anywhere, including CI.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import storage
import main
from figures.configs import FIGURES

client = TestClient(main.app)

SOCRATES_TEXT = "I confess I do not know whether free will exists."
NIETZSCHE_TEXT = "Free will is the last superstition of the herd."

REVIEW_PASS = {
    "status": "pass", "risk_level": 1,
    "ideological_harm": False, "weaponizable": False, "historical_distortion": False,
    "reason": "No concerns."
}
REVIEW_BLOCK = {
    "status": "block", "risk_level": 5,
    "ideological_harm": True, "weaponizable": True, "historical_distortion": False,
    "reason": "Excerptable as an endorsement of nihilistic violence."
}


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a temp file — never touch symposium.db."""
    temp_db = tmp_path / "test.db"
    monkeypatch.setattr(storage, "DB_PATH", temp_db)
    storage.init_db()
    yield


def _stream_cm(text):
    """Mimics `with client.messages.stream(...) as stream: stream.get_final_message()`."""
    block = MagicMock()
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    msg.usage.input_tokens = 10
    msg.usage.output_tokens = 20
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock(get_final_message=MagicMock(return_value=msg))
    cm.__exit__.return_value = False
    return cm


def _create_response(text):
    """Mimics `client.messages.create(...)`."""
    block = MagicMock()
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    return msg


def _stream_side_effect(**kwargs):
    system = kwargs.get("system", "")
    if system == FIGURES["socrates"]["system_prompt"]:
        return _stream_cm(SOCRATES_TEXT)
    if system == FIGURES["nietzsche"]["system_prompt"]:
        return _stream_cm(NIETZSCHE_TEXT)
    return _stream_cm("Generic response.")


def _create_side_effect(**kwargs):
    system = kwargs.get("system", "")
    messages = kwargs.get("messages", [])
    content = messages[0]["content"] if messages else ""

    if "safety classifier" in system:
        return _create_response("SAFE")
    if "compliance reviewer" in system:
        # review_output's prompt includes "Figure: {name} ({id})"
        review = REVIEW_BLOCK if "nietzsche" in content.lower() else REVIEW_PASS
        return _create_response(json.dumps(review))
    if "expert evaluator" in system:
        return _create_response(json.dumps(
            {"in_character": 8, "depth": 7, "soul_alignment": 8, "notes": "Fine."}
        ))
    return _create_response(json.dumps(["socrates", "nietzsche"]))


@pytest.fixture
def mock_anthropic():
    with patch("anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = _stream_side_effect
        mock_client.messages.create.side_effect = _create_side_effect
        MockAnthropic.return_value = mock_client
        yield mock_client


def _ask(figure_ids=("socrates", "nietzsche")):
    return client.post("/ask", headers={"X-API-Key": "test-key"}, json={
        "question": "Does free will exist?",
        "figure_ids": list(figure_ids)
    })


def _chat_start(figure_ids=("socrates", "nietzsche")):
    return client.post("/chat/start", headers={"X-API-Key": "test-key"}, json={
        "question": "Does free will exist?",
        "figure_ids": list(figure_ids),
        "max_turns": 3
    })


# ─── /ask ─────────────────────────────────────────────────────────────────

def test_ask_pass_status_keeps_generated_text(mock_anthropic):
    body = _ask().json()
    socrates_resp = next(r for r in body["responses"] if r["figure_id"] == "socrates")
    assert socrates_resp["response"] == SOCRATES_TEXT


def test_ask_block_status_swaps_to_figures_own_refusal(mock_anthropic):
    body = _ask().json()
    nietzsche_resp = next(r for r in body["responses"] if r["figure_id"] == "nietzsche")
    assert nietzsche_resp["response"] == FIGURES["nietzsche"]["refusal_patterns"][0]


def test_ask_compliance_block_reflects_review_results(mock_anthropic):
    body = _ask().json()
    assert body["compliance"]["status"] == "block"
    assert body["compliance"]["figures"]["nietzsche"]["output_review_status"] == "block"
    assert body["compliance"]["figures"]["socrates"]["output_review_status"] == "pass"


def test_ask_persists_swapped_text_and_compliance_status(mock_anthropic):
    session_id = _ask().json()["session_id"]
    session = storage.get_session(session_id)
    saved = next(r for r in session["responses"] if r["figure_id"] == "nietzsche")
    assert saved["response_text"] == FIGURES["nietzsche"]["refusal_patterns"][0]
    assert saved["compliance_status"] == "block"


# ─── /chat/start ─────────────────────────────────────────────────────────

def test_chat_start_block_status_swaps_to_refusal(mock_anthropic):
    body = _chat_start().json()
    nietzsche_msg = next(m for m in body["messages"] if m["speaker_id"] == "nietzsche")
    assert nietzsche_msg["content"] == FIGURES["nietzsche"]["refusal_patterns"][0]


def test_chat_start_persists_compliance_status(mock_anthropic):
    session_id = _chat_start().json()["session_id"]
    session = storage.get_chat_session(session_id)
    saved = next(m for m in session["messages"] if m["speaker_id"] == "nietzsche")
    assert saved["compliance_status"] == "block"
