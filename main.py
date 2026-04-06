"""
Symposium — FastAPI backend
Symposium — history's greatest minds, convened to answer your questions.
"""

import concurrent.futures
import json
from dotenv import load_dotenv
load_dotenv(override=True)
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from typing import Optional
import anthropic

from figures.configs import FIGURES
from law import check_harm
from panel import get_all_figures, get_figure, select_panel, get_active_tensions
from storage import (
    init_db, save_session, save_response, save_quality_scores,
    save_rating, get_session, get_history, get_quality_stats,
    save_chat_session, save_chat_message, update_chat_turn,
    get_chat_session, get_chat_history
)
from chat import (
    select_next_speakers, generate_opening_round,
    generate_reply_round, generate_closing_round
)
from quality import score_response
from compliance import (
    check_figure_eligibility, review_output,
    build_compliance_block, FIGURE_REGISTRY
)

app = FastAPI(
    title="Symposium",
    description="Symposium — history's greatest minds, convened to answer your questions.",
    version="0.2.0"
)

# Initialize DB on startup
init_db()


def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="X-API-Key header is required. Provide your Anthropic API key."
        )
    return x_api_key


# ─── Request / Response models ─────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    figure_ids: Optional[list[str]] = None
    panel_size: int = 4

class PanelSuggestRequest(BaseModel):
    question: str
    size: int = 4

class RateRequest(BaseModel):
    session_id: str
    figure_id: str
    rating: int          # 1–5
    note: Optional[str] = None

class FigureResponse(BaseModel):
    figure_id: str
    name: str
    role: str
    soul_signature: str
    response: str

class TensionHighlight(BaseModel):
    figure_a: str
    figure_b: str
    description: str

class AskResponse(BaseModel):
    session_id: str
    question: str
    panel: list[dict]
    responses: list[FigureResponse]
    tensions: list[TensionHighlight]
    compliance: dict


class ChatStartRequest(BaseModel):
    question: str
    figure_ids: Optional[list[str]] = None
    panel_size: int = 4
    max_turns: int = 10         # user messages before closing round

class ChatMessageRequest(BaseModel):
    message: str

class ChatMessageOut(BaseModel):
    turn: int
    speaker_id: str
    speaker_name: str
    role: Optional[str] = None
    content: str
    is_closing: bool = False

class ChatTurnResponse(BaseModel):
    session_id: str
    turn: int
    turns_remaining: int
    is_closing: bool
    is_complete: bool
    messages: list[ChatMessageOut]
    token_usage: dict


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "Symposium",
        "version": "0.2.0",
        "endpoints": {
            "GET  /figures":                  "List all available figures",
            "GET  /figures/{id}":             "Get a specific figure's profile",
            "POST /panel/suggest":            "Get panel recommendation for a question",
            "POST /ask":                      "Ask the panel a question (single round)",
            "GET  /history":                  "Browse past /ask sessions",
            "GET  /history/{session_id}":     "Get a specific session with full responses",
            "POST /rate":                     "Rate a figure's response (1–5)",
            "GET  /quality":                  "Aggregate quality scores per figure",
            "POST /chat/start":               "Start a group chat session",
            "POST /chat/{session_id}":        "Send a message — returns 1-2 figure replies",
            "GET  /chats":                    "Browse past chat sessions",
            "GET  /chat/{session_id}":        "Full chat history with token usage"
        }
    }


@app.get("/figures")
def list_figures(api_key: str = Depends(require_api_key)):
    return {
        "figures": [
            {
                "id": f["id"],
                "name": f["name"],
                "category": f["category"],
                "era": f["era"],
                "role": f["role"],
                "soul_signature": f["soul_signature"]
            }
            for f in FIGURES.values()
        ]
    }


@app.get("/figures/{figure_id}")
def figure_detail(figure_id: str, api_key: str = Depends(require_api_key)):
    figure = get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail=f"Figure '{figure_id}' not found")
    return {k: v for k, v in figure.items() if k not in ("system_prompt",)}


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


@app.post("/ask", response_model=AskResponse)
def ask_panel(request: AskRequest, background_tasks: BackgroundTasks, api_key: str = Depends(require_api_key)):
    """Ask the panel. Responses are saved and auto-scored in the background."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question cannot be empty")

    # ── Law layer ──────────────────────────────────────────────────────────
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

    # ── Select panel ───────────────────────────────────────────────────────
    figure_ids = request.figure_ids or select_panel(question, request.panel_size, api_key)

    # Principle 5 + 6: eligibility check before any generation
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

    # ── Generate responses in parallel ─────────────────────────────────────
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

    # ── Save to DB ─────────────────────────────────────────────────────────
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

    # ── Auto-score + compliance review in background (non-blocking) ───────
    background_tasks.add_task(
        _score_all_responses, question, figures, raw_responses, response_ids, api_key
    )
    background_tasks.add_task(
        _review_all_outputs, question, figures, raw_responses, session_id, api_key
    )

    # ── Build response ─────────────────────────────────────────────────────
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

    # Principle 1: compliance block always present — review pending until background completes
    compliance = build_compliance_block(figure_ids)

    return AskResponse(
        session_id=session_id,
        question=question,
        panel=[{"id": f["id"], "name": f["name"], "role": f["role"]} for f in figures],
        responses=responses,
        tensions=tensions,
        compliance=compliance
    )


@app.get("/history")
def history(limit: int = 20, offset: int = 0, api_key: str = Depends(require_api_key)):
    """Browse past sessions (summary view)."""
    return {"sessions": get_history(limit, offset)}


@app.get("/history/{session_id}")
def session_detail(session_id: str, api_key: str = Depends(require_api_key)):
    """Full session: question, all responses, quality scores, user ratings."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


@app.post("/rate")
def rate_response(request: RateRequest, api_key: str = Depends(require_api_key)):
    """Rate a figure's response in a session (1–5 stars)."""
    if not 1 <= request.rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    if request.figure_id not in [r["figure_id"] for r in session["responses"]]:
        raise HTTPException(status_code=404, detail="figure not in this session")
    save_rating(request.session_id, request.figure_id, request.rating, request.note)
    return {"status": "saved", "session_id": request.session_id,
            "figure_id": request.figure_id, "rating": request.rating}


@app.get("/quality")
def quality_stats(api_key: str = Depends(require_api_key)):
    """Aggregate quality scores and user ratings per figure."""
    return {"figures": get_quality_stats()}


@app.get("/compliance")
def compliance_registry(api_key: str = Depends(require_api_key)):
    """Show compliance status for all figures — copyright, eligibility, production readiness."""
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


# ─── Chat endpoints ────────────────────────────────────────────────────────

@app.post("/chat/start", response_model=ChatTurnResponse)
def chat_start(request: ChatStartRequest, api_key: str = Depends(require_api_key)):
    """
    Start a group chat. Returns the opening round — all figures respond to
    the question. Use the returned session_id for subsequent /chat/{id} calls.
    """
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

    # Opening round — all figures, no prior history
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


@app.post("/chat/{session_id}", response_model=ChatTurnResponse)
def chat_message(session_id: str, request: ChatMessageRequest, api_key: str = Depends(require_api_key)):
    """
    Send a message to the panel. Returns 1–2 figure responses.
    When the last allowed turn is reached, also returns closing statements
    from all figures and marks the session complete.
    """
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

    # Load full history for context
    history = [
        {
            "speaker_id": m["speaker_id"],
            "speaker_name": m["speaker_name"],
            "content": m["content"],
            "is_closing": bool(m["is_closing"])
        }
        for m in session["messages"]
    ]

    # Save user message
    save_chat_message(
        session_id=session_id, turn=turns_used,
        speaker_id="user", speaker_name="You",
        role=None, content=message
    )
    history.append({"speaker_id": "user", "speaker_name": "You",
                    "content": message, "is_closing": False})

    # Select next speakers based on collision proximity
    next_ids = select_next_speakers("user", figures, history, n=2)
    next_figures = [FIGURES[fid] for fid in next_ids if fid in FIGURES]

    reply_results = generate_reply_round(next_figures, session["question"], history, api_key)

    turn_input = sum(r[2] for r in reply_results)
    turn_output = sum(r[3] for r in reply_results)

    # Include user message first so the turn response is self-contained
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

    # If this was the last turn, append closing statements from all figures
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


@app.get("/chats")
def list_chats(limit: int = 20, offset: int = 0, api_key: str = Depends(require_api_key)):
    """Browse past chat sessions with question, status, and token usage."""
    return {"sessions": get_chat_history(limit, offset)}


@app.get("/chat/{session_id}")
def chat_history(session_id: str, api_key: str = Depends(require_api_key)):
    """Full chat history — all turns, all speakers, token totals."""
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="chat session not found")
    return session


# ─── Internal helpers ──────────────────────────────────────────────────────

def _ask_figure(figure: dict, question: str, api_key: str) -> str:
    """Get a single figure's response. Called in a thread pool."""
    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=figure["system_prompt"],
        messages=[{"role": "user", "content": question}]
    ) as stream:
        final = stream.get_final_message()
        for block in reversed(final.content):
            if hasattr(block, "text"):
                return block.text
        return ""


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
