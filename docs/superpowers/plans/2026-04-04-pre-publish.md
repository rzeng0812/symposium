# Symposium Pre-Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire BYOK (per-request API key via `X-API-Key` header), add `high_sensitivity` flag to five litigious figures, sanitize repo for public release (CLAUDE.md, personal scripts, gitignore), update `watch.py` for BYOK, add AGPL-3.0 LICENSE, and write README — making the repo ready to go public.

**Architecture:** The Anthropic client is currently created once at module level in six files. We remove all module-level clients and thread `api_key: str` as an explicit parameter through every function that calls Anthropic. FastAPI's `Depends()` extracts the key from the `X-API-Key` header once at the endpoint boundary; everything downstream receives it as a plain argument.

**Tech Stack:** FastAPI, Python 3.13, `anthropic` SDK, `pytest` + `requests` for integration tests (live server required).

---

## File map

| File | Change |
|------|--------|
| `law.py` | Remove module-level `_client`; add `api_key` param to `check_harm` |
| `quality.py` | Remove module-level `_client`; add `api_key` param to `score_response` |
| `compliance.py` | Remove module-level `_client`; add `api_key` param to `review_output`; add `high_sensitivity` field to 5 figures |
| `panel.py` | Remove module-level `_client`; add `api_key` param to `select_panel` |
| `chat.py` | Remove module-level `_client`; thread `api_key` through `_call_figure → _safe_call → _run_parallel → generate_*` |
| `main.py` | Remove module-level `_client`; add `require_api_key` dependency; add `api_key` to `_ask_figure`, `_score_all_responses`, `_review_all_outputs`; add `Depends(require_api_key)` to every endpoint; update existing tests to pass `X-API-Key` header |
| `watch.py` | Add `--api-key` flag + `SYMPOSIUM_API_KEY` env fallback; pass key in `X-API-Key` header |
| `.gitignore` | Add `docs/superpowers/`, `run_conversation.py`, `summarise_for_zh.py` |
| `CLAUDE.md` | Replace with trimmed architecture-only version (remove roadmap, legal notes, internal checklist) |
| `.env.example` | Create — note that no env vars are required after BYOK |
| `LICENSE` | Create — AGPL-3.0 full text |
| `README.md` | Create — setup, BYOK, API overview, disclaimer requirement, license |

---

## Task 1: BYOK — law.py, quality.py, compliance.py

**Files:**
- Modify: `law.py`
- Modify: `quality.py`
- Modify: `compliance.py`
- Modify: `tests/test_api.py`

These three files each have a module-level `_client = anthropic.Anthropic()` and a single function that uses it. The fix is identical in each: remove the module-level client, accept `api_key: str`, and create the client inline.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (these will pass once Task 4 wires the header, but writing them now documents the contract):

```python
import os, requests

BASE = "http://localhost:8765"
API_KEY = os.environ["ANTHROPIC_API_KEY"]

def test_ask_requires_api_key():
    """Missing X-API-Key → 401."""
    r = requests.post(f"{BASE}/ask", json={"question": "What is truth?", "panel_size": 2})
    assert r.status_code == 401, r.text

def test_ask_with_api_key_succeeds():
    """Valid X-API-Key → 200 with compliance disclaimer."""
    r = requests.post(
        f"{BASE}/ask",
        headers={"X-API-Key": API_KEY},
        json={"question": "What is truth?", "panel_size": 2}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "compliance" in body
    assert "disclaimer" in body["compliance"]
```

- [ ] **Step 2: Run to confirm both tests fail**

```bash
uvicorn main:app --port 8765 &
sleep 3
pytest tests/test_api.py::test_ask_requires_api_key tests/test_api.py::test_ask_with_api_key_succeeds -v
```

Expected: both FAIL — `test_ask_requires_api_key` fails because the server returns 200 (not 401); `test_ask_with_api_key_succeeds` may pass or fail depending on server env key. That's fine — we proceed.

- [ ] **Step 3: Update law.py**

Replace the entire file with:

```python
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
```

- [ ] **Step 4: Update quality.py**

Replace the entire file with:

```python
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


def score_response(figure_id: str, question: str, response_text: str,
                   api_key: str) -> dict:
    """
    Score a single figure response. Returns score dict or defaults on failure.
    """
    figure = FIGURES.get(figure_id)
    if not figure:
        return {"in_character": 0, "depth": 0, "soul_alignment": 0, "notes": "Unknown figure."}

    soul_profile = f"""Name: {figure['name']}
Soul signature: {figure['soul_signature']}
Role: {figure['role']}
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
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=SCORER_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"in_character": None, "depth": None, "soul_alignment": None,
                "notes": "Scoring failed."}
```

- [ ] **Step 5: Update compliance.py — remove module-level client, add api_key to review_output**

Two targeted edits. First, remove the module-level client (line 18):

```python
# DELETE this line:
_client = anthropic.Anthropic()
```

Second, update `review_output` signature and body:

```python
def review_output(figure_id: str, figure_name: str, question: str,
                  response_text: str, api_key: str) -> dict:
    """
    Post-generation output review. Enforces Principle 7.
    Called as a background task — does not block the main response.

    Returns compliance assessment dict.
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
        return {
            "status": "review",
            "risk_level": 3,
            "ideological_harm": False,
            "weaponizable": False,
            "historical_distortion": False,
            "reason": "Compliance review failed — manual review recommended."
        }
```

- [ ] **Step 6: Commit**

```bash
git add law.py quality.py compliance.py tests/test_api.py
git commit -m "feat: add api_key param to law, quality, compliance — BYOK prep"
```

---

## Task 2: BYOK — panel.py

**Files:**
- Modify: `panel.py`

- [ ] **Step 1: Remove module-level client; add api_key to select_panel**

Replace the entire file with:

```python
"""
Panel selection — picks the figures with maximum collision potential for a given question.
"""

import json
import anthropic
from figures.configs import FIGURES, DEFAULT_PANEL


def get_all_figures() -> list[dict]:
    return list(FIGURES.values())


def get_figure(figure_id: str) -> dict | None:
    return FIGURES.get(figure_id)


def select_panel(question: str, size: int = 4, api_key: str = "") -> list[str]:
    """
    Use Claude to select the panel with maximum intellectual tension for a question.
    Falls back to the default panel on failure.
    """
    figure_list = "\n".join([
        f"- {f['id']}: {f['name']} ({f['role']}) — {f['soul_signature']}"
        for f in FIGURES.values()
    ])

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=128,
            system=f"""You select the most intellectually interesting panel to answer a question.

Available figures:
{figure_list}

Select exactly {size} figures that will produce maximum intellectual tension and worldview diversity when answering the question. Prefer combinations where figures have fundamentally different epistemic methods, values, or approaches to truth.

The most interesting panels include:
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

    return DEFAULT_PANEL[:size]


def get_active_tensions(figure_ids: list[str]) -> list[dict]:
    """
    Return the collision trigger pairs that exist within a given panel.
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
```

- [ ] **Step 2: Commit**

```bash
git add panel.py
git commit -m "feat: add api_key param to select_panel — BYOK prep"
```

---

## Task 3: BYOK — chat.py

**Files:**
- Modify: `chat.py`

The key is that `api_key` flows from the three public functions (`generate_opening_round`, `generate_reply_round`, `generate_closing_round`) down through `_run_parallel → _safe_call → _call_figure`.

- [ ] **Step 1: Replace chat.py**

```python
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

    recent = [m["speaker_id"] for m in history[-8:] if m["speaker_id"] != "user"]

    if last_speaker_id != "user":
        triggered = [
            f["id"] for f in eligible
            if last_speaker_id in f.get("collision_triggers", {})
        ]
        if triggered:
            triggered.sort(key=lambda fid: recent.count(fid))
            return triggered[:n]

    eligible.sort(key=lambda f: recent.count(f["id"]))
    return [f["id"] for f in eligible[:n]]


# ─── Single-figure response ─────────────────────────────────────────────────

def _call_figure(figure: dict, question: str, history: list[dict],
                 closing: bool, api_key: str) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)."""
    template = _CLOSING_PROMPT if closing else _CHAT_PROMPT
    user_content = template.format(
        question=question,
        history=_format_history(history)
    )
    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
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


def _safe_call(figure: dict, question: str, history: list[dict],
               closing: bool, api_key: str) -> tuple[str, str, int, int]:
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

def _run_parallel(figures: list[dict], question: str, history: list[dict],
                  closing: bool, api_key: str) -> list[tuple]:
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


def generate_opening_round(figures: list[dict], question: str,
                            api_key: str) -> list[tuple]:
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
```

- [ ] **Step 2: Commit**

```bash
git add chat.py
git commit -m "feat: thread api_key through chat.py — BYOK prep"
```

---

## Task 4: BYOK — main.py (wire it all together)

**Files:**
- Modify: `main.py`
- Modify: `tests/test_api.py`

This is the integration point. We add a `require_api_key` dependency, remove the module-level client, update every endpoint, and update the three internal helpers.

- [ ] **Step 1: Add imports and require_api_key dependency to main.py**

Add `Depends, Header` to the FastAPI import and `Optional` to typing:

```python
# Replace existing FastAPI import line:
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
# Replace existing typing import line:
from typing import Optional
```

Add `require_api_key` right after the `app = FastAPI(...)` block and before `_client = anthropic.Anthropic()`:

```python
def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="X-API-Key header is required. Provide your Anthropic API key."
        )
    return x_api_key
```

- [ ] **Step 2: Remove the module-level client**

Delete this line from main.py:

```python
_client = anthropic.Anthropic()
```

- [ ] **Step 3: Update _ask_figure helper**

```python
def _ask_figure(figure: dict, question: str, api_key: str) -> str:
    """Get a single figure's response. Called in a thread pool."""
    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=figure["system_prompt"],
        messages=[{"role": "user", "content": question}]
    ) as stream:
        final = stream.get_final_message()
        for block in reversed(final.content):
            if hasattr(block, "text"):
                return block.text
        return ""
```

- [ ] **Step 4: Update _score_all_responses and _review_all_outputs helpers**

```python
def _score_all_responses(question: str, figures: list, raw_responses: dict,
                          response_ids: dict, api_key: str):
    """Background task: score all responses after they've been returned to the user."""
    for fig in figures:
        fid = fig["id"]
        scores = score_response(fid, question, raw_responses[fid], api_key)
        if scores.get("in_character") is not None:
            save_quality_scores(
                response_id=response_ids[fid],
                in_character=scores["in_character"],
                depth=scores["depth"],
                soul_alignment=scores["soul_alignment"],
                notes=scores.get("notes", "")
            )


def _review_all_outputs(question: str, figures: list, raw_responses: dict,
                         session_id: str, api_key: str):
    """Background task: run Principle 7 output review on all responses."""
    import sqlite3
    from storage import get_conn
    for fig in figures:
        fid = fig["id"]
        result = review_output(fid, fig["name"], question, raw_responses[fid], api_key)
        with get_conn() as conn:
            conn.execute("""
                UPDATE responses SET
                    compliance_status=?,
                    compliance_risk_level=?,
                    compliance_flags=?,
                    compliance_reason=?
                WHERE session_id=? AND figure_id=?
            """, (
                result.get("status"),
                result.get("risk_level"),
                json.dumps({
                    "ideological_harm": result.get("ideological_harm"),
                    "weaponizable": result.get("weaponizable"),
                    "historical_distortion": result.get("historical_distortion")
                }),
                result.get("reason"),
                session_id, fid
            ))
```

- [ ] **Step 5: Update all endpoints to accept api_key via Depends**

For each endpoint below, add `api_key: str = Depends(require_api_key)` to the signature and update the call sites as shown.

**`/panel/suggest`:**
```python
@app.post("/panel/suggest")
def suggest_panel(request: PanelSuggestRequest, api_key: str = Depends(require_api_key)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    figure_ids = select_panel(request.question, request.size, api_key)
    return {
        "question": request.question,
        "panel": [
            {
                "id": fid,
                "name": FIGURES[fid]["name"],
                "role": FIGURES[fid]["role"],
                "soul_signature": FIGURES[fid]["soul_signature"]
            }
            for fid in figure_ids
        ],
        "tensions": get_active_tensions(figure_ids)
    }
```

**`/ask`:**
```python
@app.post("/ask", response_model=AskResponse)
def ask_panel(request: AskRequest, background_tasks: BackgroundTasks,
              api_key: str = Depends(require_api_key)):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question cannot be empty")

    harm = check_harm(question, api_key)
    if not harm["safe"]:
        figure_ids = request.figure_ids or list(FIGURES.keys())[:2]
        raise HTTPException(
            status_code=400,
            detail={
                "error": "question_flagged",
                "in_character_refusals": [
                    {
                        "figure_id": fid,
                        "name": FIGURES[fid]["name"],
                        "response": FIGURES[fid]["refusal_patterns"][0]
                    }
                    for fid in figure_ids if fid in FIGURES
                ]
            }
        )

    figure_ids = request.figure_ids or select_panel(question, request.panel_size, api_key)

    blocked = []
    for fid in figure_ids:
        eligibility = check_figure_eligibility(fid)
        if not eligibility["eligible"]:
            blocked.append({"figure_id": fid, "reason": eligibility["reason"]})
    if blocked:
        raise HTTPException(status_code=400, detail={
            "error": "figures_ineligible",
            "blocked": blocked
        })

    figures = [FIGURES[fid] for fid in figure_ids if fid in FIGURES]
    if not figures:
        raise HTTPException(status_code=400, detail="No valid figures selected")

    raw_responses: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(figures)) as executor:
        future_to_figure = {
            executor.submit(_ask_figure, fig, question, api_key): fig
            for fig in figures
        }
        for future, figure in future_to_figure.items():
            try:
                raw_responses[figure["id"]] = future.result(timeout=60)
            except Exception:
                raw_responses[figure["id"]] = (
                    f"[{figure['name']} was lost in thought and could not respond.]"
                )

    session_id = save_session(question, figure_ids)
    response_ids: dict[str, int] = {}
    for fig in figures:
        rid = save_response(
            session_id=session_id,
            figure_id=fig["id"],
            figure_name=fig["name"],
            role=fig["role"],
            response_text=raw_responses[fig["id"]]
        )
        response_ids[fig["id"]] = rid

    background_tasks.add_task(
        _score_all_responses, question, figures, raw_responses, response_ids, api_key
    )
    background_tasks.add_task(
        _review_all_outputs, question, figures, raw_responses, session_id, api_key
    )

    id_order = {fid: i for i, fid in enumerate(figure_ids)}
    responses = sorted([
        FigureResponse(
            figure_id=fig["id"],
            name=fig["name"],
            role=fig["role"],
            soul_signature=fig["soul_signature"],
            response=raw_responses[fig["id"]]
        )
        for fig in figures
    ], key=lambda r: id_order.get(r.figure_id, 999))

    tensions = [TensionHighlight(**t) for t in get_active_tensions(figure_ids)]
    compliance = build_compliance_block(figure_ids)

    return AskResponse(
        session_id=session_id,
        question=question,
        panel=[{"id": f["id"], "name": f["name"], "role": f["role"]} for f in figures],
        responses=responses,
        tensions=tensions,
        compliance=compliance
    )
```

**`/chat/start`:**
```python
@app.post("/chat/start", response_model=ChatTurnResponse)
def chat_start(request: ChatStartRequest, api_key: str = Depends(require_api_key)):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question cannot be empty")

    harm = check_harm(question, api_key)
    if not harm["safe"]:
        raise HTTPException(status_code=400, detail={"error": "question_flagged"})

    figure_ids = request.figure_ids or select_panel(question, request.panel_size, api_key)

    for fid in figure_ids:
        eligibility = check_figure_eligibility(fid)
        if not eligibility["eligible"]:
            raise HTTPException(status_code=400, detail={
                "error": "figures_ineligible",
                "blocked": [{"figure_id": fid, "reason": eligibility["reason"]}]
            })

    figures = [FIGURES[fid] for fid in figure_ids if fid in FIGURES]
    if not figures:
        raise HTTPException(status_code=400, detail="No valid figures selected")

    session_id = save_chat_session(question, figure_ids, request.max_turns)
    results = generate_opening_round(figures, question, api_key)

    turn_input = sum(r[2] for r in results)
    turn_output = sum(r[3] for r in results)

    messages_out = []
    for fid, text, inp, out in results:
        fig = FIGURES[fid]
        save_chat_message(
            session_id=session_id, turn=0,
            speaker_id=fid, speaker_name=fig["name"],
            role=fig["role"], content=text,
            is_closing=False, input_tokens=inp, output_tokens=out
        )
        messages_out.append(ChatMessageOut(
            turn=0, speaker_id=fid, speaker_name=fig["name"],
            role=fig["role"], content=text, is_closing=False
        ))

    update_chat_turn(session_id, turns_used=0,
                     added_input=turn_input, added_output=turn_output)

    return ChatTurnResponse(
        session_id=session_id,
        turn=0,
        turns_remaining=request.max_turns,
        is_closing=False,
        is_complete=False,
        messages=messages_out,
        token_usage={"input_tokens": turn_input, "output_tokens": turn_output}
    )
```

**`/chat/{session_id}`:**
```python
@app.post("/chat/{session_id}", response_model=ChatTurnResponse)
def chat_message(session_id: str, request: ChatMessageRequest,
                 api_key: str = Depends(require_api_key)):
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="chat session not found")
    if session["status"] == "complete":
        raise HTTPException(status_code=400, detail="this conversation has ended")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")

    figure_ids = session["panel_ids"]
    figures = [FIGURES[fid] for fid in figure_ids if fid in FIGURES]
    turns_used = session["turns_used"] + 1
    is_last_turn = turns_used >= session["max_turns"]

    history = [
        {
            "speaker_id": m["speaker_id"],
            "speaker_name": m["speaker_name"],
            "content": m["content"],
            "is_closing": bool(m["is_closing"])
        }
        for m in session["messages"]
    ]

    save_chat_message(
        session_id=session_id, turn=turns_used,
        speaker_id="user", speaker_name="You",
        role=None, content=message
    )
    history.append({"speaker_id": "user", "speaker_name": "You",
                    "content": message, "is_closing": False})

    next_ids = select_next_speakers("user", figures, history, n=2)
    next_figures = [FIGURES[fid] for fid in next_ids if fid in FIGURES]

    reply_results = generate_reply_round(next_figures, session["question"], history, api_key)

    turn_input = sum(r[2] for r in reply_results)
    turn_output = sum(r[3] for r in reply_results)

    messages_out = [ChatMessageOut(
        turn=turns_used, speaker_id="user", speaker_name="You",
        role=None, content=message, is_closing=False
    )]

    for fid, text, inp, out in reply_results:
        fig = FIGURES[fid]
        save_chat_message(
            session_id=session_id, turn=turns_used,
            speaker_id=fid, speaker_name=fig["name"],
            role=fig["role"], content=text,
            is_closing=False, input_tokens=inp, output_tokens=out
        )
        history.append({"speaker_id": fid, "speaker_name": fig["name"],
                        "content": text, "is_closing": False})
        messages_out.append(ChatMessageOut(
            turn=turns_used, speaker_id=fid, speaker_name=fig["name"],
            role=fig["role"], content=text, is_closing=False
        ))

    if is_last_turn:
        closing_results = generate_closing_round(figures, session["question"], history, api_key)
        for fid, text, inp, out in closing_results:
            fig = FIGURES[fid]
            turn_input += inp
            turn_output += out
            save_chat_message(
                session_id=session_id, turn=turns_used,
                speaker_id=fid, speaker_name=fig["name"],
                role=fig["role"], content=text,
                is_closing=True, input_tokens=inp, output_tokens=out
            )
            messages_out.append(ChatMessageOut(
                turn=turns_used, speaker_id=fid, speaker_name=fig["name"],
                role=fig["role"], content=text, is_closing=True
            ))

    status = "complete" if is_last_turn else "active"
    update_chat_turn(session_id, turns_used=turns_used,
                     added_input=turn_input, added_output=turn_output,
                     status=status)

    return ChatTurnResponse(
        session_id=session_id,
        turn=turns_used,
        turns_remaining=max(0, session["max_turns"] - turns_used),
        is_closing=is_last_turn,
        is_complete=is_last_turn,
        messages=messages_out,
        token_usage={"input_tokens": turn_input, "output_tokens": turn_output}
    )
```

**Read-only endpoints** (`/figures`, `/figures/{id}`, `/history`, `/history/{session_id}`, `/rate`, `/quality`, `/compliance`, `/chats`, `/chat/{session_id}` GET) also get `api_key: str = Depends(require_api_key)` added to their signatures. They don't use it, but it enforces the header requirement consistently.

Example — apply this pattern to each remaining endpoint:
```python
@app.get("/figures")
def list_figures(api_key: str = Depends(require_api_key)):
    ...

@app.get("/figures/{figure_id}")
def figure_detail(figure_id: str, api_key: str = Depends(require_api_key)):
    ...

@app.get("/history")
def history(limit: int = 20, offset: int = 0, api_key: str = Depends(require_api_key)):
    ...

@app.get("/history/{session_id}")
def session_detail(session_id: str, api_key: str = Depends(require_api_key)):
    ...

@app.post("/rate")
def rate_response(request: RateRequest, api_key: str = Depends(require_api_key)):
    ...

@app.get("/quality")
def quality_stats(api_key: str = Depends(require_api_key)):
    ...

@app.get("/compliance")
def compliance_registry(api_key: str = Depends(require_api_key)):
    ...

@app.get("/chats")
def list_chats(limit: int = 20, offset: int = 0, api_key: str = Depends(require_api_key)):
    ...
```

The root `GET /` endpoint is the only one that stays unauthenticated — it just returns the endpoint list and is safe to leave public.

- [ ] **Step 6: Update tests/test_api.py — add X-API-Key header to all existing requests**

Read the existing test file. Find every `requests.get(...)` and `requests.post(...)` call and add `headers={"X-API-Key": API_KEY}` (or merge it with any existing headers dict). The `API_KEY = os.environ["ANTHROPIC_API_KEY"]` line added in Task 1 provides the value.

- [ ] **Step 7: Kill the running server, restart, and run the two new tests**

```bash
pkill -f "uvicorn main:app" || true
uvicorn main:app --port 8765 &
sleep 3
pytest tests/test_api.py::test_ask_requires_api_key tests/test_api.py::test_ask_with_api_key_succeeds -v
```

Expected: both PASS.

- [ ] **Step 8: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass. If any fail because they're missing the `X-API-Key` header, add it.

- [ ] **Step 9: Commit**

```bash
git add main.py tests/test_api.py
git commit -m "feat: wire BYOK — X-API-Key header required on all endpoints"
```

---

## Task 5: high_sensitivity flag in compliance.py

**Files:**
- Modify: `compliance.py`

Five figures have active, litigious estates that have pursued action even for non-commercial use: Kahlo (Frida Kahlo Corporation), Warhol (Andy Warhol Foundation), Picasso (Picasso Administration), Jobs (Apple Inc. as active party), Morrison (recently formed estate). Add a `high_sensitivity` field to their `FIGURE_REGISTRY` entries and surface it in the `/compliance` endpoint response.

- [ ] **Step 1: Add high_sensitivity field to the five entries in FIGURE_REGISTRY**

In `compliance.py`, find each of the five entries and add `"high_sensitivity": True`. All other entries get `"high_sensitivity": False` (or you may omit the field for non-sensitive entries and default to `False` in the endpoint). The explicit approach is clearest:

```python
# kahlo entry — add:
"high_sensitivity": True,
"high_sensitivity_notes": (
    "Frida Kahlo Corporation (Banco de México) has pursued legal action "
    "for non-commercial educational use. Include additional care in generated content."
),

# warhol entry — add:
"high_sensitivity": True,
"high_sensitivity_notes": (
    "Andy Warhol Foundation has litigated aggressively across all use contexts, "
    "including a landmark 2023 Supreme Court case narrowing fair use."
),

# picasso entry — add:
"high_sensitivity": True,
"high_sensitivity_notes": (
    "Picasso Administration actively blocks likeness use; even educational "
    "and editorial use has been challenged."
),

# jobs entry — add:
"high_sensitivity": True,
"high_sensitivity_notes": (
    "Apple Inc. is an active party in rights management alongside the Jobs estate, "
    "making this a corporate-backed claim rather than a family estate."
),

# morrison entry — add:
"high_sensitivity": True,
"high_sensitivity_notes": (
    "Toni Morrison Estate was established in 2019 and is still forming its "
    "enforcement posture — uncertainty makes this higher risk."
),
```

- [ ] **Step 2: Update build_compliance_block to include high_sensitivity**

In `build_compliance_block`, add `high_sensitivity` to the per-figure status dict:

```python
figure_statuses[fid] = {
    "copyright_status": entry.get("copyright_status", "unknown"),
    "production_ready": entry.get("production_ready", False),
    "high_sensitivity": entry.get("high_sensitivity", False),
    "output_review_status": review.get("status", "pending"),
    "output_risk_level": review.get("risk_level", None)
}
```

- [ ] **Step 3: Update the /compliance endpoint to include high_sensitivity**

```python
@app.get("/compliance")
def compliance_registry(api_key: str = Depends(require_api_key)):
    return {
        "figures": {
            fid: {
                "living": entry["living"],
                "copyright_status": entry["copyright_status"],
                "production_ready": entry["production_ready"],
                "high_sensitivity": entry.get("high_sensitivity", False),
                "high_sensitivity_notes": entry.get("high_sensitivity_notes", ""),
                "copyright_notes": entry["copyright_notes"]
            }
            for fid, entry in FIGURE_REGISTRY.items()
        },
        "principles": {
            "1": "Identity transparency — disclaimer on every response",
            "5": "No living people",
            "6": "Copyright as citizenship — cleared before use",
            "7": "Harm threshold is effect — output reviewed post-generation"
        }
    }
```

- [ ] **Step 4: Commit**

```bash
git add compliance.py
git commit -m "feat: add high_sensitivity flag to kahlo, warhol, picasso, jobs, morrison"
```

---

## Task 6: LICENSE

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create LICENSE with AGPL-3.0 text**

Create `LICENSE` at the repo root with the full AGPL-3.0 license text. The canonical text is at https://www.gnu.org/licenses/agpl-3.0.txt — copy it verbatim. The first two lines should be:

```
                    GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007
```

Do not modify the license text. Do not add a copyright header line above it — the README will document the copyright holder.

- [ ] **Step 2: Commit**

```bash
git add LICENSE
git commit -m "chore: add AGPL-3.0 license"
```

---

## Task 7: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

```markdown
# Symposium

AI-powered panels of historical figures, convened to answer your questions.

Socrates interrogates. Nietzsche declares. Einstein calculates. You ask.

## What it is

Symposium is a FastAPI backend that convenes panels of historical figures to engage
with questions across philosophy, science, ethics, and history. Each figure has a
detailed soul configuration — voice, values, refusals, collision triggers — and the
platform selects panels for maximum intellectual tension.

**Self-hostable. BYOK. Open source under AGPL-3.0.**

## Quickstart

Requires Python 3.13+ and an [Anthropic API key](https://console.anthropic.com).

```bash
git clone https://github.com/your-org/symposium
cd symposium
pip install -r requirements.txt
uvicorn main:app --reload --port 8765
```

The server starts on `http://localhost:8765`. No environment variables required — you
supply your API key per request.

## BYOK — Bring Your Own Key

Symposium does not manage API keys. You supply your Anthropic API key with every
request via the `X-API-Key` header:

```bash
curl -X POST http://localhost:8765/ask \
  -H "X-API-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"question": "Does free will exist?", "panel_size": 4}'
```

Your key is passed directly to the Anthropic API and is never stored or logged.

## API overview

All endpoints require the `X-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Endpoint index |
| GET | `/figures` | List all 101 figures |
| GET | `/figures/{id}` | Get a specific figure's profile |
| POST | `/panel/suggest` | Recommend a panel for a question |
| POST | `/ask` | Single-round panel response |
| GET | `/history` | Browse past sessions |
| GET | `/history/{id}` | Full session with responses and scores |
| POST | `/rate` | Rate a figure response (1–5) |
| GET | `/quality` | Aggregate quality scores per figure |
| POST | `/chat/start` | Start a multi-turn group chat |
| POST | `/chat/{id}` | Send a message, receive replies |
| GET | `/chats` | Browse past chat sessions |
| GET | `/chat/{id}` | Full chat history |
| GET | `/compliance` | Copyright and eligibility status per figure |

### Example: single-round ask

```bash
curl -X POST http://localhost:8765/ask \
  -H "X-API-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the relationship between power and truth?"}'
```

### Example: multi-turn chat

```bash
# Start a chat
curl -X POST http://localhost:8765/chat/start \
  -H "X-API-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"question": "Does consciousness require a body?"}'

# Continue with a message (use the session_id from the response above)
curl -X POST http://localhost:8765/chat/SESSION_ID \
  -H "X-API-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"message": "But what about dreams?"}'
```

## Disclaimer requirement

Every `/ask` and `/chat` response includes a `compliance.disclaimer` field:

> AI-generated interpretation. Not a real quote or verified historical position.
> Symposium reconstructs figures from documented sources — responses reflect
> informed interpretation, not the actual words or views of these individuals.

**Frontends built on Symposium are required to display this disclaimer to users.**
This is a non-negotiable condition of use under AGPL-3.0.

## Content safety

Symposium has three built-in safety layers:

1. **Pre-generation harm classification** — every question is classified before any
   figure responds. Harmful requests trigger in-character refusals instead of
   generic error messages.

2. **Figure eligibility check** — no living people (hardcoded), copyright status
   verified before generation.

3. **Post-generation output review** — responses are reviewed for ideological harm,
   weaponizable content, and historical distortion after generation.

## Running tests

Tests require a live server and a valid Anthropic API key:

```bash
uvicorn main:app --port 8765 &
ANTHROPIC_API_KEY=sk-ant-... pytest tests/ -v
```

## License

[AGPL-3.0](LICENSE)

Derivative works — including services that deploy Symposium — must also be released
under AGPL-3.0. This prevents commercial forks from exploiting the IP protections
that the open-source, non-commercial status provides.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with BYOK, API overview, and disclaimer requirement"
```

---

---

## Task 8a: Repo sanitization

**Files:**
- Modify: `.gitignore`
- Modify: `CLAUDE.md`
- Create: `.env.example`

- [ ] **Step 1: Update .gitignore**

Add these lines to `.gitignore`:

```
# Internal AI planning docs
docs/superpowers/

# Personal local scripts (not for public release)
run_conversation.py
summarise_for_zh.py
```

- [ ] **Step 2: Replace CLAUDE.md with a trimmed contributor-facing version**

The existing `CLAUDE.md` contains private project notes (roadmap status, internal legal decisions, pre-publish checklists) that don't belong in a public repo. Replace it with an architecture-only version useful for contributors:

```markdown
# Symposium — Architecture Notes

## What This Is

Symposium is a FastAPI backend that convenes panels of historical figures to answer
questions. Each figure has a soul config, harm layer, copyright compliance tracking,
and post-generation output review.

## Architecture

- **Backend:** FastAPI (`main.py`), Python 3.13
- **Figure configs:** `figures/configs.py` — soul prompts, collision triggers, refusal patterns
- **Panel selection:** `panel.py` — Claude-powered panel selection for max intellectual tension
- **Chat:** `chat.py` — multi-turn group conversation with speaker selection
- **Safety:** `law.py` — pre-generation harm classification (SAFE/UNSAFE)
- **Compliance:** `compliance.py` — figure eligibility, post-generation output review, disclaimer
- **Quality:** `quality.py` — auto-scoring of responses (in_character, depth, soul_alignment)
- **Storage:** `storage.py` — SQLite (`symposium.db`), sessions, responses, quality scores, ratings
- **Watch:** `watch.py` — CLI tool to watch conversations in real time (Rich or plain)
- **Tests:** `tests/test_api.py` — integration tests, requires live server

## BYOK

All endpoints require `X-API-Key` header. The key is passed to `anthropic.Anthropic(api_key=...)`
per request — never stored or logged.

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8765
python watch.py "Does free will exist?" --panel socrates nietzsche feynman --api-key sk-ant-...
```

## Product Principles

See `PRINCIPLES.md` — 7 principles enforced in code.

## Model

`claude-opus-4-6` throughout.
```

- [ ] **Step 3: Create .env.example**

```bash
# .env.example
#
# No server-side environment variables are required.
# Supply your Anthropic API key per request via the X-API-Key header:
#
#   curl -H "X-API-Key: sk-ant-..." http://localhost:8765/ask ...
#
# For local development convenience, watch.py accepts --api-key or
# reads SYMPOSIUM_API_KEY from the environment.
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore CLAUDE.md .env.example
git commit -m "chore: sanitize repo for public release — trim CLAUDE.md, gitignore personal scripts"
```

---

## Task 8b: watch.py BYOK

**Files:**
- Modify: `watch.py`

`watch.py` calls every API endpoint via `_post` and `_get`. After BYOK is wired on the server, all requests need `X-API-Key`. The CLI should accept `--api-key` and fall back to the `SYMPOSIUM_API_KEY` environment variable (so developers can `export SYMPOSIUM_API_KEY=sk-ant-...` once and not type it every invocation).

- [ ] **Step 1: Update _post and _get to accept and send api_key**

Replace the `_post` and `_get` functions:

```python
def _post(path: str, data: dict, api_key: str) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        print(f"\n[ERROR {e.code}] {detail}")
        sys.exit(1)


def _get(path: str, api_key: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"X-API-Key": api_key},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError:
        print(f"\n[ERROR] Cannot reach server at {BASE}")
        print("Start it with:  uvicorn main:app --port 8765")
        sys.exit(1)
```

- [ ] **Step 2: Add --api-key argument and resolve key in main()**

Add to the `argparse` block in `main()`:

```python
parser.add_argument(
    "--api-key",
    default=os.environ.get("SYMPOSIUM_API_KEY", ""),
    help="Anthropic API key (or set SYMPOSIUM_API_KEY env var)"
)
```

Add `import os` at the top of the file.

After `args = parser.parse_args()`, add key validation:

```python
api_key = args.api_key
if not api_key:
    print("[ERROR] Anthropic API key required.")
    print("  Pass --api-key sk-ant-... or set SYMPOSIUM_API_KEY environment variable.")
    sys.exit(1)
```

- [ ] **Step 3: Thread api_key through all _post and _get call sites**

Every call to `_post` and `_get` in `main()` and `_pick_panel()` needs `api_key` passed as the final argument. The call sites are:

```python
# _pick_panel — update signature and call:
def _pick_panel(api_key: str) -> list[str] | None:
    data = _get("/figures", api_key)
    ...

# In main(), update _pick_panel call:
panel_ids = _pick_panel(api_key)   # None = auto

# All _post calls in main():
data = _post("/chat/start", payload, api_key)
data = _post(f"/chat/{session_id}", {"message": user_msg}, api_key)
```

- [ ] **Step 4: Commit**

```bash
git add watch.py
git commit -m "feat: add --api-key flag and X-API-Key header to watch.py"
```

---

## Self-review

**Spec coverage check:**

| Requirement | Task |
|-------------|------|
| Accept `X-API-Key` header on all endpoints | Task 4 |
| Pass to `anthropic.Anthropic(api_key=...)` per request | Tasks 1–4 |
| Never store or log key | Covered — no storage calls touch the key |
| Validate key present, return clear error if missing | Task 4 → 401 |
| `review_needed` figures — open source low risk | Existing code allows them |
| 5 high-sensitivity figures flagged | Task 5 |
| LICENSE — AGPL-3.0 | Task 6 |
| README | Task 7 |
| Repo sanitized (CLAUDE.md, personal scripts, gitignore) | Task 8a |
| watch.py BYOK | Task 8b |

**Placeholder scan:** No TBDs or vague steps found.

**Type consistency check:** `api_key: str` is used consistently. `select_panel` defaults `api_key=""` for the fallback path; all production callers provide it via `Depends(require_api_key)`.
