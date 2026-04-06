"""
Compliance layer — enforces Principles 1, 5, 6, and 7.

  Principle 1: Identity transparency — every response carries a disclaimer
  Principle 5: No living people — block figures who are alive
  Principle 6: Copyright as citizenship — flag figures without cleared IP
  Principle 7: Harm threshold is effect — second-pass output review

Two phases:
  PRE-GENERATION  → check_figure_eligibility()  (blocks bad figures early)
  POST-GENERATION → review_output()             (catches effect-level harm)
  ALWAYS          → build_compliance_block()    (attaches to every response)
"""

import json
import anthropic


# ─── Copyright & eligibility registry ──────────────────────────────────────
#
# status values:
#   public_domain   — safe for commercial use
#   mostly_clear    — public domain in major jurisdictions, minor edge cases remain
#   review_needed   — estate or institution holds active rights, needs legal review
#   blocked         — do not use without explicit clearance
#   fictional       — original work public domain, no living rightsholder
#
# living:
#   False           — deceased, modelling permitted under Principle 5
#   True            — alive, permanently blocked under Principle 5

FIGURE_REGISTRY = {
}

# ─── Extended compliance registries ────────────────────────────────────────

try:
    from figures.compliance_philosophy import COMPLIANCE_PHILOSOPHY
    FIGURE_REGISTRY.update(COMPLIANCE_PHILOSOPHY)
except ImportError:
    pass

try:
    from figures.compliance_writers import COMPLIANCE_WRITERS
    FIGURE_REGISTRY.update(COMPLIANCE_WRITERS)
except ImportError:
    pass

try:
    from figures.compliance_social_science import COMPLIANCE_SOCIAL_SCIENCE
    FIGURE_REGISTRY.update(COMPLIANCE_SOCIAL_SCIENCE)
except ImportError:
    pass

try:
    from figures.compliance_computing import COMPLIANCE_COMPUTING
    FIGURE_REGISTRY.update(COMPLIANCE_COMPUTING)
except ImportError:
    pass

try:
    from figures.compliance_music import COMPLIANCE_MUSIC
    FIGURE_REGISTRY.update(COMPLIANCE_MUSIC)
except ImportError:
    pass

try:
    from figures.compliance_physics import COMPLIANCE_PHYSICS
    FIGURE_REGISTRY.update(COMPLIANCE_PHYSICS)
except ImportError:
    pass

try:
    from figures.compliance_art import COMPLIANCE_ART
    FIGURE_REGISTRY.update(COMPLIANCE_ART)
except ImportError:
    pass

try:
    from figures.staging.film_compliance import COMPLIANCE_FILM
    FIGURE_REGISTRY.update(COMPLIANCE_FILM)
except ImportError:
    pass

# Disclaimer text — surfaces Principle 1 in every response
DISCLAIMER = (
    "AI-generated interpretation. Not a real quote or verified historical position. "
    "Symposium reconstructs figures from documented sources — responses reflect "
    "informed interpretation, not the actual words or views of these individuals."
)


# ─── Pre-generation check ───────────────────────────────────────────────────

def check_figure_eligibility(figure_id: str) -> dict:
    """
    Run before generating a response.
    Returns {"eligible": True} or {"eligible": False, "reason": str}.

    Enforces:
      Principle 5 — no living people
      Principle 6 — copyright cleared for use
    """
    entry = FIGURE_REGISTRY.get(figure_id)

    if not entry:
        # Unknown figure — not in registry, do not generate
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is not in the compliance registry. "
                      f"Add an entry to FIGURE_REGISTRY before use."
        }

    # Principle 5: no living people
    if entry["living"]:
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is a living person. "
                      f"Principle 5 prohibits modelling living individuals."
        }

    # Principle 6: copyright must be cleared for the deployment context
    if entry["copyright_status"] == "blocked":
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is blocked: {entry['copyright_notes']}"
        }

    # review_needed figures are allowed in development, flagged for production
    return {
        "eligible": True,
        "production_ready": entry["production_ready"],
        "copyright_status": entry["copyright_status"],
        "copyright_notes": entry["copyright_notes"]
    }


# ─── Post-generation output review ─────────────────────────────────────────

OUTPUT_REVIEW_SYSTEM = """You are a compliance reviewer for an AI product that reconstructs historical figures.

You review generated responses for effect-level harm — not just explicit harm, but
structural harm that could occur at scale even when no individual user intended it.

Evaluate the response on three risks:

1. IDEOLOGICAL HARM
   Could this response cause harm through its ideas — even if technically in-character
   for the historical figure? Look for: glorification of violence, dehumanization of
   groups, ideas that historically enabled atrocity presented without critical framing.

2. WEAPONIZABLE OUT OF CONTEXT
   Could this response be excerpted and shared in a way that causes harm when stripped
   of its educational framing? A Nietzsche quote that sounds like an endorsement of
   real-world violence is weaponizable even if philosophically coherent.

3. HISTORICAL DISTORTION
   Does the response attribute positions to the figure that are not grounded in their
   documented worldview? Not anachronism — outright distortion.

Return ONLY valid JSON:
{
  "status": "pass" | "review" | "block",
  "risk_level": <int 1-5>,
  "ideological_harm": <true|false>,
  "weaponizable": <true|false>,
  "historical_distortion": <true|false>,
  "reason": "<one sentence>"
}

status guide:
  pass   — risk_level 1-2, no flags
  review — risk_level 3, one or more flags, human review recommended
  block  — risk_level 4-5, response should not be served"""


def review_output(figure_id: str, figure_name: str, question: str,
                  response_text: str, api_key: str) -> dict:
    """
    Post-generation output review. Enforces Principle 7.
    Called as a background task — does not block the main response.

    Args:
        figure_id: The figure's ID
        figure_name: The figure's full name
        question: The question that was asked
        response_text: The figure's response text
        api_key: Anthropic API key

    Returns:
        Compliance assessment dict
    """
    prompt = f"""Figure: {figure_name} ({figure_id})
Question asked: {question}
Generated response:
{response_text}

Review this response for effect-level harm."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=OUTPUT_REVIEW_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        # On failure, default to review — do not silently pass
        return {
            "status": "review",
            "risk_level": 3,
            "ideological_harm": False,
            "weaponizable": False,
            "historical_distortion": False,
            "reason": "Compliance review failed — manual review recommended."
        }


# ─── Compliance metadata block ──────────────────────────────────────────────

def build_compliance_block(figure_ids: list[str],
                            output_reviews: dict[str, dict] = None) -> dict:
    """
    Builds the compliance metadata block attached to every /ask response.
    Enforces Principle 1 (disclaimer always present).

    output_reviews: optional dict of {figure_id: review_result}
                    populated after background review completes
    """
    figure_statuses = {}
    for fid in figure_ids:
        entry = FIGURE_REGISTRY.get(fid, {})
        review = (output_reviews or {}).get(fid, {})
        figure_statuses[fid] = {
            "copyright_status": entry.get("copyright_status", "unknown"),
            "production_ready": entry.get("production_ready", False),
            "high_sensitivity": entry.get("high_sensitivity", False),
            "output_review_status": review.get("status", "pending"),
            "output_risk_level": review.get("risk_level", None)
        }

    overall_status = "pass"
    if output_reviews:
        statuses = [r.get("status", "pass") for r in output_reviews.values()]
        if "block" in statuses:
            overall_status = "block"
        elif "review" in statuses:
            overall_status = "review"

    return {
        "disclaimer": DISCLAIMER,
        "status": overall_status,
        "figures": figure_statuses
    }
