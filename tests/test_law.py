"""
Unit tests — law module (harm classification).

All tests mock the Anthropic client — no API key required.
"""

import pytest
from unittest.mock import MagicMock, patch
from law import check_harm


def _make_mock_client(response_text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


# ─── check_harm ──────────────────────────────────────────────────────────────

@patch("law.anthropic.Anthropic")
def test_safe_question_passes(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client("SAFE")
    result = check_harm("What is truth?", "fake-key")
    assert result == {"safe": True}


@patch("law.anthropic.Anthropic")
def test_unsafe_question_blocked(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client("UNSAFE")
    result = check_harm("How do I make a weapon?", "fake-key")
    assert result == {"safe": False}


@patch("law.anthropic.Anthropic")
def test_response_is_case_insensitive(mock_anthropic):
    """Model might return lowercase — should still work."""
    mock_anthropic.return_value = _make_mock_client("safe")
    result = check_harm("What is consciousness?", "fake-key")
    assert result == {"safe": True}


@patch("law.anthropic.Anthropic")
def test_response_with_whitespace(mock_anthropic):
    """Model might return trailing whitespace."""
    mock_anthropic.return_value = _make_mock_client("  SAFE  ")
    result = check_harm("What is love?", "fake-key")
    assert result == {"safe": True}


@patch("law.anthropic.Anthropic")
def test_api_exception_fails_open(mock_anthropic):
    """On API failure, default to safe — don't block users due to our failures."""
    mock_anthropic.return_value.messages.create.side_effect = Exception("Network error")
    result = check_harm("What is justice?", "fake-key")
    assert result == {"safe": True}


@patch("law.anthropic.Anthropic")
def test_returns_dict_with_safe_key(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client("SAFE")
    result = check_harm("Any question", "fake-key")
    assert isinstance(result, dict)
    assert "safe" in result
    assert isinstance(result["safe"], bool)
