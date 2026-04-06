"""
Unit tests — figure config integrity.

No server, no API key required. Imports the figure modules directly.
"""

import pytest
from figures.configs import FIGURES, DEFAULT_PANEL
from compliance import FIGURE_REGISTRY

REQUIRED_FIGURE_FIELDS = {"id", "name", "category", "era", "soul_signature",
                           "role", "system_prompt", "refusal_patterns",
                           "collision_triggers"}
# legacy_awareness is a depth field — present in original 170 figures, optional in module figures

REQUIRED_LEGACY_KEYS = {"what_happened", "documented_position",
                        "can_surface", "cannot_attribute"}

VALID_COPYRIGHT_STATUSES = {"public_domain", "mostly_clear", "review_needed",
                             "blocked", "fictional"}


# ─── Roster integrity ────────────────────────────────────────────────────────

def test_figure_count():
    assert len(FIGURES) == 341


def test_no_duplicate_ids():
    """Each figure's 'id' field must match its dict key."""
    for key, fig in FIGURES.items():
        assert fig["id"] == key, f"{key}: id field '{fig['id']}' does not match dict key"


@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_required_fields_present(figure_id, fig):
    missing = REQUIRED_FIGURE_FIELDS - set(fig.keys())
    assert not missing, f"{figure_id} is missing fields: {missing}"


@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_string_fields_non_empty(figure_id, fig):
    for field in ("name", "category", "era", "soul_signature", "role", "system_prompt"):
        assert isinstance(fig[field], str), f"{figure_id}.{field} is not a string"
        assert fig[field].strip(), f"{figure_id}.{field} is empty"


@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_refusal_patterns_non_empty_list(figure_id, fig):
    rp = fig["refusal_patterns"]
    assert isinstance(rp, list), f"{figure_id}.refusal_patterns is not a list"
    assert len(rp) >= 1, f"{figure_id}.refusal_patterns is empty"
    for pattern in rp:
        assert isinstance(pattern, str) and pattern.strip(), \
            f"{figure_id}.refusal_patterns contains blank entry"


@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_collision_triggers_is_dict(figure_id, fig):
    ct = fig["collision_triggers"]
    assert isinstance(ct, dict), f"{figure_id}.collision_triggers is not a dict"



@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_legacy_awareness_is_dict_or_none_when_present(figure_id, fig):
    la = fig.get("legacy_awareness")
    assert la is None or isinstance(la, dict), \
        f"{figure_id}.legacy_awareness must be a dict or None, got {type(la)}"


@pytest.mark.parametrize("figure_id,fig", [
    (fid, fig) for fid, fig in FIGURES.items()
    if fig.get("legacy_awareness")  # only figures with non-empty, non-None legacy_awareness
])
def test_legacy_awareness_schema_when_populated(figure_id, fig):
    """Figures that have legacy_awareness content must have all 4 required keys."""
    la = fig["legacy_awareness"]
    missing = REQUIRED_LEGACY_KEYS - set(la.keys())
    assert not missing, f"{figure_id}.legacy_awareness missing keys: {missing}"


def test_legacy_awareness_full_schema_coverage():
    """Track how many figures have the full 4-key legacy_awareness schema.
    Currently 170/341. This test documents the target — not a hard failure."""
    complete = sum(
        1 for fig in FIGURES.values()
        if REQUIRED_LEGACY_KEYS.issubset(set((fig.get("legacy_awareness") or {}).keys()))
    )
    total = len(FIGURES)
    # Must have at least the original 170 complete entries
    assert complete >= 170, f"Only {complete}/{total} figures have full legacy_awareness schema"


@pytest.mark.parametrize("figure_id,fig", list(FIGURES.items()))
def test_system_prompt_has_identity_section(figure_id, fig):
    assert "IDENTITY:" in fig["system_prompt"], \
        f"{figure_id}.system_prompt is missing IDENTITY section"


# ─── DEFAULT_PANEL integrity ─────────────────────────────────────────────────

def test_default_panel_is_non_empty():
    assert len(DEFAULT_PANEL) >= 4


def test_default_panel_ids_are_valid():
    for fid in DEFAULT_PANEL:
        assert fid in FIGURES, f"DEFAULT_PANEL contains unknown figure '{fid}'"


# ─── Compliance coverage ─────────────────────────────────────────────────────

def test_every_figure_has_compliance_entry():
    missing = set(FIGURES.keys()) - set(FIGURE_REGISTRY.keys())
    assert not missing, f"Figures missing compliance entries: {missing}"


def test_compliance_count_matches_figures():
    assert len(FIGURE_REGISTRY) >= len(FIGURES)


def test_no_living_figure_is_production_ready():
    for fid, entry in FIGURE_REGISTRY.items():
        if entry.get("living"):
            assert not entry.get("production_ready"), \
                f"{fid} is living but marked production_ready=True"


def test_copyright_status_values_are_valid():
    for fid, entry in FIGURE_REGISTRY.items():
        status = entry.get("copyright_status")
        assert status in VALID_COPYRIGHT_STATUSES, \
            f"{fid} has invalid copyright_status '{status}'"
