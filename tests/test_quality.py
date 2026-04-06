"""
Unit tests — quality scorer.

Unknown figure case requires no API. Scoring tests mock the Anthropic client.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from quality import score_response


VALID_SCORE_RESPONSE = json.dumps({
    "in_character": 8,
    "depth": 7,
    "soul_alignment": 9,
    "notes": "Strong voice, philosophically grounded."
})


def _make_mock_client(text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


# ─── score_response ──────────────────────────────────────────────────────────

def test_unknown_figure_returns_zero_scores():
    result = score_response("definitely_not_a_figure", "What is truth?", "Some response.", "fake-key")
    assert result["in_character"] == 0
    assert result["depth"] == 0
    assert result["soul_alignment"] == 0
    assert "Unknown figure" in result["notes"]


@patch("quality.anthropic.Anthropic")
def test_valid_response_parsed(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client(VALID_SCORE_RESPONSE)
    result = score_response("socrates", "What is truth?", "I know nothing.", "fake-key")
    assert result["in_character"] == 8
    assert result["depth"] == 7
    assert result["soul_alignment"] == 9
    assert isinstance(result["notes"], str)


@patch("quality.anthropic.Anthropic")
def test_strips_markdown_fences(mock_anthropic):
    wrapped = f"```json\n{VALID_SCORE_RESPONSE}\n```"
    mock_anthropic.return_value = _make_mock_client(wrapped)
    result = score_response("socrates", "What is truth?", "I know nothing.", "fake-key")
    assert result["in_character"] == 8


@patch("quality.anthropic.Anthropic")
def test_api_exception_returns_none_scores(mock_anthropic):
    mock_anthropic.return_value.messages.create.side_effect = Exception("API error")
    result = score_response("socrates", "What is truth?", "I know nothing.", "fake-key")
    assert result["in_character"] is None
    assert result["depth"] is None
    assert result["soul_alignment"] is None
    assert "failed" in result["notes"].lower()


@patch("quality.anthropic.Anthropic")
def test_result_has_required_keys(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client(VALID_SCORE_RESPONSE)
    result = score_response("nietzsche", "What is power?", "Power is will.", "fake-key")
    assert set(result.keys()) >= {"in_character", "depth", "soul_alignment", "notes"}


@patch("quality.anthropic.Anthropic")
def test_scores_are_integers(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client(VALID_SCORE_RESPONSE)
    result = score_response("nietzsche", "What is power?", "Power is will.", "fake-key")
    assert isinstance(result["in_character"], int)
    assert isinstance(result["depth"], int)
    assert isinstance(result["soul_alignment"], int)
