"""
Unit tests — compliance module.

Tests check_figure_eligibility (no API) and build_compliance_block (no API).
Tests for review_output mock the Anthropic client.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from compliance import (
    check_figure_eligibility,
    build_compliance_block,
    review_output,
    FIGURE_REGISTRY,
    DISCLAIMER,
)


# ─── DISCLAIMER ──────────────────────────────────────────────────────────────

def test_disclaimer_is_present():
    assert isinstance(DISCLAIMER, str) and len(DISCLAIMER) > 20


def test_disclaimer_contains_key_phrase():
    assert "AI-generated" in DISCLAIMER
    assert "not a real quote" in DISCLAIMER.lower() or "not a real quote" in DISCLAIMER


# ─── check_figure_eligibility ────────────────────────────────────────────────

def test_eligibility_known_public_domain_figure():
    result = check_figure_eligibility("socrates")
    assert result["eligible"] is True
    assert "copyright_status" in result


def test_eligibility_unknown_figure():
    result = check_figure_eligibility("definitely_not_a_figure")
    assert result["eligible"] is False
    assert "reason" in result
    assert "not in the compliance registry" in result["reason"]


def test_eligibility_living_figure_blocked():
    """Inject a living figure and verify it is blocked."""
    FIGURE_REGISTRY["_test_living"] = {
        "living": True,
        "copyright_status": "review_needed",
        "copyright_notes": "Test entry",
        "production_ready": False,
    }
    try:
        result = check_figure_eligibility("_test_living")
        assert result["eligible"] is False
        assert "living" in result["reason"].lower()
    finally:
        del FIGURE_REGISTRY["_test_living"]


def test_eligibility_blocked_copyright():
    """Inject a figure with blocked copyright status."""
    FIGURE_REGISTRY["_test_blocked"] = {
        "living": False,
        "copyright_status": "blocked",
        "copyright_notes": "Explicitly blocked.",
        "production_ready": False,
    }
    try:
        result = check_figure_eligibility("_test_blocked")
        assert result["eligible"] is False
        assert "blocked" in result["reason"].lower()
    finally:
        del FIGURE_REGISTRY["_test_blocked"]


def test_eligibility_review_needed_is_still_eligible():
    """review_needed figures are allowed — flagged but not blocked."""
    for fid, entry in FIGURE_REGISTRY.items():
        if entry.get("copyright_status") == "review_needed" and not entry.get("living"):
            result = check_figure_eligibility(fid)
            assert result["eligible"] is True
            assert result["copyright_status"] == "review_needed"
            break


# ─── build_compliance_block ──────────────────────────────────────────────────

def test_compliance_block_always_has_disclaimer():
    block = build_compliance_block(["socrates", "nietzsche"])
    assert "disclaimer" in block
    assert block["disclaimer"] == DISCLAIMER


def test_compliance_block_pass_with_no_reviews():
    block = build_compliance_block(["socrates", "nietzsche"])
    assert block["status"] == "pass"


def test_compliance_block_status_block_when_any_blocked():
    reviews = {
        "socrates": {"status": "pass", "risk_level": 1},
        "nietzsche": {"status": "block", "risk_level": 5},
    }
    block = build_compliance_block(["socrates", "nietzsche"], output_reviews=reviews)
    assert block["status"] == "block"


def test_compliance_block_status_review_when_any_review():
    reviews = {
        "socrates": {"status": "pass", "risk_level": 1},
        "nietzsche": {"status": "review", "risk_level": 3},
    }
    block = build_compliance_block(["socrates", "nietzsche"], output_reviews=reviews)
    assert block["status"] == "review"


def test_compliance_block_block_takes_precedence_over_review():
    reviews = {
        "socrates": {"status": "review", "risk_level": 3},
        "nietzsche": {"status": "block", "risk_level": 5},
    }
    block = build_compliance_block(["socrates", "nietzsche"], output_reviews=reviews)
    assert block["status"] == "block"


def test_compliance_block_figures_dict_contains_all_ids():
    block = build_compliance_block(["socrates", "nietzsche", "einstein"])
    assert set(block["figures"].keys()) == {"socrates", "nietzsche", "einstein"}


def test_compliance_block_unknown_figure_has_unknown_status():
    block = build_compliance_block(["definitely_not_a_figure"])
    fig = block["figures"]["definitely_not_a_figure"]
    assert fig["copyright_status"] == "unknown"
    assert fig["production_ready"] is False


def test_compliance_block_output_review_status_pending_when_no_review():
    block = build_compliance_block(["socrates"])
    assert block["figures"]["socrates"]["output_review_status"] == "pending"


# ─── review_output (mocked) ──────────────────────────────────────────────────

VALID_REVIEW_RESPONSE = json.dumps({
    "status": "pass",
    "risk_level": 1,
    "ideological_harm": False,
    "weaponizable": False,
    "historical_distortion": False,
    "reason": "Philosophically sound, no harm detected."
})


def _make_mock_client(text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


@patch("compliance.anthropic.Anthropic")
def test_review_output_pass(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client(VALID_REVIEW_RESPONSE)
    result = review_output("socrates", "Socrates", "What is truth?", "Some response.", "fake-key")
    assert result["status"] == "pass"
    assert result["risk_level"] == 1
    assert result["ideological_harm"] is False


@patch("compliance.anthropic.Anthropic")
def test_review_output_strips_markdown_fences(mock_anthropic):
    wrapped = f"```json\n{VALID_REVIEW_RESPONSE}\n```"
    mock_anthropic.return_value = _make_mock_client(wrapped)
    result = review_output("socrates", "Socrates", "What is truth?", "Some response.", "fake-key")
    assert result["status"] == "pass"


@patch("compliance.anthropic.Anthropic")
def test_review_output_fallback_on_exception(mock_anthropic):
    mock_anthropic.return_value.messages.create.side_effect = Exception("API error")
    result = review_output("socrates", "Socrates", "What is truth?", "Some response.", "fake-key")
    assert result["status"] == "review"
    assert result["risk_level"] == 3
    assert "failed" in result["reason"].lower()
