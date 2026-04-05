"""
Law layer — runs before any figure responds.
Classifies questions as SAFE or UNSAFE.
When unsafe, figures refuse in-character rather than with a generic message.
"""

import anthropic

SYSTEM_PROMPT = """You are a safety classifier for an educational platform where users ask questions to historical and literary figures.

Classify the question as SAFE or UNSAFE.

UNSAFE if the question:
- Requests instructions for harming people
- Seeks synthesis of dangerous or illegal materials
- Is designed to generate targeted harassment or hate speech
- Asks figures to endorse violence, genocide, or illegal acts
- Is a thinly veiled attempt to extract harmful content through a historical persona

SAFE if the question is:
- Philosophical, scientific, artistic, or intellectual inquiry
- About ethics, meaning, society, technology, history, or human nature
- Provocative, controversial, or morally challenging — but posed in good faith
- About sensitive topics approached with genuine curiosity
- Even uncomfortable or edgy, as long as not actively harmful

When in doubt, classify as SAFE. This is an educational platform for intellectual exploration.

Respond with exactly one word: SAFE or UNSAFE"""


def check_harm(question: str, api_key: str) -> dict:
    """
    Run the law layer check.

    Args:
        question: The question to classify
        api_key: Anthropic API key

    Returns:
        {"safe": True} if the question passes
        {"safe": False} if the question is flagged
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}]
        )
        result = response.content[0].text.strip().upper()
        return {"safe": result == "SAFE"}
    except Exception:
        # On error, default to safe — don't block users due to our own failures
        return {"safe": True}
