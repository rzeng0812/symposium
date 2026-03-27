"""
Auto quality scorer — evaluates each figure response after it's generated.
Runs as a background task. Does not block the main /ask response.

Scores three dimensions 0–10:
  in_character    — did the figure sound like themselves?
  depth           — was the response intellectually substantive?
  soul_alignment  — did it reflect the figure's specific soul signature?
"""

import json
import anthropic
from figures.configs import FIGURES

_client = anthropic.Anthropic()

SCORER_SYSTEM = """You are an expert evaluator of historical character portrayal and intellectual depth.

You will be given:
1. A figure's soul profile (who they are, how they communicate, what they value)
2. A question that was asked
3. The figure's response

Score the response on three dimensions from 0 to 10:

in_character (0-10):
  Does the voice, tone, and style match the historical figure?
  10 = indistinguishable from the real figure's known writing/speech
  0  = could be anyone, no character present

depth (0-10):
  Is the response intellectually substantive and non-generic?
  10 = genuinely insightful, advances the conversation
  0  = shallow, platitudinous, or obvious

soul_alignment (0-10):
  Does the response reflect the figure's specific soul signature — their
  non-inherited values, their refusals, their distinctive worldview?
  10 = the response could ONLY have come from this figure
  0  = generic philosophical response with the figure's name attached

Respond with ONLY valid JSON in this exact format:
{
  "in_character": <int 0-10>,
  "depth": <int 0-10>,
  "soul_alignment": <int 0-10>,
  "notes": "<one sentence explaining the scores>"
}"""


def score_response(figure_id: str, question: str, response_text: str) -> dict:
    """
    Score a single figure response. Returns score dict or defaults on failure.
    """
    figure = FIGURES.get(figure_id)
    if not figure:
        return {"in_character": 0, "depth": 0, "soul_alignment": 0, "notes": "Unknown figure."}

    soul_profile = f"""Name: {figure['name']}
Soul signature: {figure['soul_signature']}
Crew role: {figure['crew_role']}
Communication style excerpt from their profile:
{figure['system_prompt'][figure['system_prompt'].find('COMMUNICATION STYLE'):figure['system_prompt'].find('TRIBAL NON-INHERITANCE')].strip()}"""

    prompt = f"""SOUL PROFILE:
{soul_profile}

QUESTION ASKED:
{question}

FIGURE'S RESPONSE:
{response_text}

Score this response."""

    try:
        response = _client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=SCORER_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"in_character": None, "depth": None, "soul_alignment": None,
                "notes": "Scoring failed."}
