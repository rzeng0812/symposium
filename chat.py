"""
Group chat orchestration for Symposium.

Turn model:
  Turn 0  — opening round: all figures respond to the question in parallel
  Turn 1–N — user sends a message: 1-2 figures respond (chosen by collision proximity)
  Turn N+1 — closing round: all figures give closing statements, session complete

Speaker selection priority:
  1. Figures whose collision_triggers include the last speaker
  2. Figures who haven't spoken most recently (round-robin fallback)
"""

import concurrent.futures
import anthropic

# ─── Prompt templates ──────────────────────────────────────────────────────

_CHAT_PROMPT = """\
ONGOING GROUP CONVERSATION
Opening question: {question}

{history}
---
Respond now. You may address other participants by name, push back on what was just \
said, continue your own line of thought, or respond to the user directly.
This is conversation, not lecture — keep your response under 150 words.
Stay fully in character."""

_CLOSING_PROMPT = """\
ONGOING GROUP CONVERSATION
Opening question: {question}

{history}
---
This conversation is ending. Give your closing statement — what has been confirmed, \
challenged, or left unresolved for you by this exchange?
Under 100 words. In character. No need to address anyone — speak to what the \
conversation revealed."""


# ─── History formatting ─────────────────────────────────────────────────────

def _format_history(messages: list[dict]) -> str:
    parts = []
    for msg in messages:
        label = msg["speaker_name"]
        if msg.get("is_closing"):
            label += " [closing]"
        parts.append(f"{label}:\n{msg['content']}")
    return "\n\n".join(parts)


# ─── Speaker selection ──────────────────────────────────────────────────────

def select_next_speakers(last_speaker_id: str, panel: list[dict],
                          history: list[dict], n: int = 2) -> list[str]:
    """
    Pick the next 1–2 speakers.

    After a figure speaks: prefer figures with a collision_trigger for that figure.
    After the user speaks: prefer figures who haven't spoken most recently.
    Fallback: round-robin by recency.
    """
    eligible = [f for f in panel if f["id"] != last_speaker_id]
    if not eligible:
        return [panel[0]["id"]]

    # Track how recently each figure spoke (lower = more recent)
    recent = [m["speaker_id"] for m in history[-8:] if m["speaker_id"] != "user"]

    if last_speaker_id != "user":
        # Find figures triggered by the last speaker
        triggered = [
            f["id"] for f in eligible
            if last_speaker_id in f.get("collision_triggers", {})
        ]
        if triggered:
            # Among triggered, prefer those who haven't spoken recently
            triggered.sort(key=lambda fid: recent.count(fid))
            return triggered[:n]

    # Fallback: least recently spoken
    eligible.sort(key=lambda f: recent.count(f["id"]))
    return [f["id"] for f in eligible[:n]]



# ─── Single-figure response ─────────────────────────────────────────────────

def _call_figure(figure: dict, question: str,
                 history: list[dict], closing: bool, api_key: str) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    client = anthropic.Anthropic(api_key=api_key)
    template = _CLOSING_PROMPT if closing else _CHAT_PROMPT
    user_content = template.format(
        question=question,
        history=_format_history(history)
    )
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=figure["system_prompt"],
        messages=[{"role": "user", "content": user_content}]
    ) as stream:
        final = stream.get_final_message()
        text = ""
        for block in reversed(final.content):
            if hasattr(block, "text"):
                text = block.text
                break
        return text, final.usage.input_tokens, final.usage.output_tokens


def _safe_call(figure: dict, question: str,
               history: list[dict], closing: bool, api_key: str) -> tuple[str, str, int, int]:
    """Wraps _call_figure with a fallback. Returns (figure_id, text, inp, out)."""
    try:
        text, inp, out = _call_figure(figure, question, history, closing, api_key)
        return figure["id"], text, inp, out
    except Exception:
        fallback = (
            f"[{figure['name']} had no closing words.]"
            if closing else
            f"[{figure['name']} was lost in thought and could not respond.]"
        )
        return figure["id"], fallback, 0, 0


# ─── Multi-figure parallel rounds ───────────────────────────────────────────

def _run_parallel(figures: list[dict], question: str,
                  history: list[dict], closing: bool, api_key: str) -> list[tuple]:
    """
    Run a set of figures in parallel.
    Returns list of (figure_id, text, input_tokens, output_tokens),
    sorted to match the original figure order.
    """
    id_order = {f["id"]: i for i, f in enumerate(figures)}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(figures)) as ex:
        futures = {
            ex.submit(_safe_call, fig, question, history, closing, api_key): fig
            for fig in figures
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: id_order.get(r[0], 999))
    return results


def generate_opening_round(figures: list[dict], question: str, api_key: str) -> list[tuple]:
    """Opening positions — all figures, no prior history."""
    return _run_parallel(figures, question, [], closing=False, api_key=api_key)


def generate_reply_round(figures: list[dict], question: str,
                          history: list[dict], api_key: str) -> list[tuple]:
    """1–2 figure replies to a user message — history includes the user turn."""
    return _run_parallel(figures, question, history, closing=False, api_key=api_key)


def generate_closing_round(figures: list[dict], question: str,
                            history: list[dict], api_key: str) -> list[tuple]:
    """All figures give closing statements."""
    return _run_parallel(figures, question, history, closing=True, api_key=api_key)
