"""
Unit tests — panel module.

get_all_figures, get_figure, get_active_tensions: no API needed.
select_panel: mocked.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from panel import get_all_figures, get_figure, get_active_tensions, select_panel
from figures.configs import FIGURES, DEFAULT_PANEL


# ─── get_all_figures ─────────────────────────────────────────────────────────

def test_get_all_figures_returns_all():
    figures = get_all_figures()
    assert len(figures) == len(FIGURES)


def test_get_all_figures_returns_dicts_with_id():
    for fig in get_all_figures():
        assert "id" in fig
        assert "name" in fig
        assert "role" in fig
        assert "soul_signature" in fig


# ─── get_figure ──────────────────────────────────────────────────────────────

def test_get_figure_known():
    fig = get_figure("socrates")
    assert fig is not None
    assert fig["id"] == "socrates"
    assert fig["name"] == "Socrates"


def test_get_figure_unknown_returns_none():
    assert get_figure("definitely_not_a_figure") is None


def test_get_figure_is_same_object_as_figures_dict():
    assert get_figure("nietzsche") is FIGURES["nietzsche"]


# ─── get_active_tensions ─────────────────────────────────────────────────────

def test_tensions_known_pair():
    """socrates and nietzsche have documented collision triggers."""
    tensions = get_active_tensions(["socrates", "nietzsche"])
    pairs = {(t["figure_a"], t["figure_b"]) for t in tensions}
    # At least one direction of the pair should appear
    assert ("socrates", "nietzsche") in pairs or ("nietzsche", "socrates") in pairs


def test_tensions_no_duplicates():
    """Each pair should appear at most once."""
    tensions = get_active_tensions(["socrates", "nietzsche", "einstein", "feynman"])
    pairs = [tuple(sorted([t["figure_a"], t["figure_b"]])) for t in tensions]
    assert len(pairs) == len(set(pairs)), "Duplicate tension pairs returned"


def test_tensions_empty_panel():
    assert get_active_tensions([]) == []


def test_tensions_single_figure():
    assert get_active_tensions(["socrates"]) == []


def test_tensions_no_overlap_panel():
    """A panel where no figures reference each other should return no tensions."""
    # Pick figures with minimal collision overlap — use a single isolated figure
    tensions = get_active_tensions(["imhotep"])
    assert tensions == []


def test_tensions_result_structure():
    tensions = get_active_tensions(["socrates", "nietzsche"])
    for t in tensions:
        assert "figure_a" in t
        assert "figure_b" in t
        assert "description" in t
        assert isinstance(t["description"], str)


def test_tensions_only_panel_members():
    """Tensions should only reference figures in the panel."""
    panel = ["socrates", "nietzsche", "einstein"]
    tensions = get_active_tensions(panel)
    for t in tensions:
        assert t["figure_a"] in panel
        assert t["figure_b"] in panel


def test_tensions_unknown_figure_ignored():
    """Unknown figure IDs should be silently skipped."""
    tensions = get_active_tensions(["socrates", "definitely_not_a_figure"])
    for t in tensions:
        assert t["figure_a"] != "definitely_not_a_figure"
        assert t["figure_b"] != "definitely_not_a_figure"


# ─── select_panel (mocked) ───────────────────────────────────────────────────

def _make_mock_client(text: str):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


@patch("panel.anthropic.Anthropic")
def test_select_panel_returns_valid_ids(mock_anthropic):
    ids = ["socrates", "nietzsche", "einstein", "feynman"]
    mock_anthropic.return_value = _make_mock_client(json.dumps(ids))
    result = select_panel("What is truth?", size=4, api_key="fake-key")
    assert result == ids


@patch("panel.anthropic.Anthropic")
def test_select_panel_filters_invalid_ids(mock_anthropic):
    """If model returns unknown IDs, they are filtered out; falls back to default if too few remain."""
    ids = ["socrates", "definitely_not_real", "nietzsche", "also_fake"]
    mock_anthropic.return_value = _make_mock_client(json.dumps(ids))
    result = select_panel("What is truth?", size=4, api_key="fake-key")
    for fid in result:
        assert fid in FIGURES


@patch("panel.anthropic.Anthropic")
def test_select_panel_falls_back_on_exception(mock_anthropic):
    mock_anthropic.return_value.messages.create.side_effect = Exception("API error")
    result = select_panel("What is truth?", size=4, api_key="fake-key")
    assert result == DEFAULT_PANEL[:4]


@patch("panel.anthropic.Anthropic")
def test_select_panel_falls_back_on_invalid_json(mock_anthropic):
    mock_anthropic.return_value = _make_mock_client("not valid json at all")
    result = select_panel("What is truth?", size=4, api_key="fake-key")
    assert result == DEFAULT_PANEL[:4]


@patch("panel.anthropic.Anthropic")
def test_select_panel_respects_size(mock_anthropic):
    ids = ["socrates", "nietzsche", "einstein", "feynman", "darwin"]
    mock_anthropic.return_value = _make_mock_client(json.dumps(ids))
    result = select_panel("What is truth?", size=3, api_key="fake-key")
    assert len(result) == 3
