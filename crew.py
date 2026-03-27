"""
Crew selection — picks the figures with maximum collision potential for a given question.
"""

import json
import anthropic
from figures.configs import FIGURES, DEFAULT_CREW

_client = anthropic.Anthropic()


def get_all_figures() -> list[dict]:
    return list(FIGURES.values())


def get_figure(figure_id: str) -> dict | None:
    return FIGURES.get(figure_id)


def select_crew(question: str, size: int = 4) -> list[str]:
    """
    Use Claude to select the crew with maximum intellectual tension for a question.
    Falls back to the default crew on failure.
    """
    figure_list = "\n".join([
        f"- {f['id']}: {f['name']} ({f['crew_role']}) — {f['soul_signature']}"
        for f in FIGURES.values()
    ])

    try:
        response = _client.messages.create(
            model="claude-opus-4-6",
            max_tokens=128,
            system=f"""You select the most intellectually interesting crew to answer a question.

Available figures:
{figure_list}

Select exactly {size} figures that will produce maximum intellectual tension and worldview diversity when answering the question. Prefer combinations where figures have fundamentally different epistemic methods, values, or approaches to truth.

The most interesting crews include:
- At least one figure who questions premises (Socrates)
- At least one figure who makes bold declarations (Nietzsche)
- Figures whose collision triggers are activated by the question's topic

Respond with ONLY a valid JSON array of figure IDs. Example: ["socrates", "einstein", "nietzsche", "sherlock_holmes"]""",
            messages=[{"role": "user", "content": f"Question: {question}"}]
        )

        raw = response.content[0].text.strip()
        ids = json.loads(raw)
        valid = [id for id in ids if id in FIGURES]
        if len(valid) >= 2:
            return valid[:size]
    except Exception:
        pass

    return DEFAULT_CREW[:size]


def get_active_tensions(figure_ids: list[str]) -> list[dict]:
    """
    Return the collision trigger pairs that exist within a given crew.
    """
    tensions = []
    seen = set()

    for fid_a in figure_ids:
        fig_a = FIGURES.get(fid_a)
        if not fig_a:
            continue
        for fid_b, description in fig_a.get("collision_triggers", {}).items():
            if fid_b in figure_ids:
                pair = tuple(sorted([fid_a, fid_b]))
                if pair not in seen:
                    seen.add(pair)
                    tensions.append({
                        "figure_a": fid_a,
                        "figure_b": fid_b,
                        "description": description
                    })

    return tensions
