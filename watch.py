#!/usr/bin/env python3
"""
watch.py — watch the panel argue in real time.

Usage:
  python watch.py
  python watch.py "What is the nature of justice?"
  python watch.py "Does free will exist?" --panel socrates nietzsche feynman
  python watch.py "Is beauty objective?" --turns 5 --size 3
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8765"

# ─── Rich formatting ─────────────────────────────────────────────────────────

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich.prompt import Prompt
    from rich.table import Table
    from rich import box
    console = Console()
    RICH = True
except ImportError:
    RICH = False


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


# ─── Speaker colours ─────────────────────────────────────────────────────────

# Assign a stable colour per figure across the session
_PALETTE = [
    "bold cyan", "bold yellow", "bold magenta",
    "bold green", "bold blue", "bold red",
]
_colour_map: dict[str, str] = {}

def _colour(speaker_id: str) -> str:
    if speaker_id == "user":
        return "bold white"
    if speaker_id not in _colour_map:
        _colour_map[speaker_id] = _PALETTE[len(_colour_map) % len(_PALETTE)]
    return _colour_map[speaker_id]


# ─── Rendering ───────────────────────────────────────────────────────────────

def _render_message(msg: dict, show_turn: bool = False):
    sid = msg["speaker_id"]
    colour = _colour(sid)

    if RICH:
        if sid == "user":
            label = ">> You"
        elif msg.get("is_closing"):
            label = f"{msg['speaker_name']} [{msg['role']}] — closing"
        else:
            label = f"{msg['speaker_name']} [{msg['role']}]"

        title = Text(label, style=colour)
        panel = Panel(
            msg["content"],
            title=title,
            title_align="left",
            border_style=colour,
            padding=(0, 1),
        )
        console.print(panel)
    else:
        # Plain ANSI fallback
        if sid == "user":
            print(f"\n>> You:")
        elif msg.get("is_closing"):
            print(f"\n{msg['speaker_name']} [{msg['role']}] — closing:")
        else:
            print(f"\n{msg['speaker_name']} [{msg['role']}]:")
        print(msg["content"])


def _section(label: str):
    if RICH:
        console.print(Rule(f"[bold]{label}[/bold]", style="dim"))
    else:
        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"{'─' * 60}")


def _token_line(usage: dict, turns_remaining: int):
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    line = f"tokens: {inp:,} in / {out:,} out  |  turns left: {turns_remaining}"
    if RICH:
        console.print(f"[dim]{line}[/dim]\n")
    else:
        print(f"\n({line})\n")


def _pick_panel(api_key: str) -> list[str] | None:
    """Interactive panel picker."""
    data = _get("/figures", api_key)
    figures = data["figures"]

    if RICH:
        t = Table(title="Available Figures", box=box.SIMPLE, show_header=True)
        t.add_column("#", style="dim", width=3)
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Role", style="dim")
        t.add_column("Soul signature", style="italic dim")
        for i, f in enumerate(figures, 1):
            t.add_row(str(i), f["id"], f["name"], f["role"], f["soul_signature"][:60])
        console.print(t)
        raw = Prompt.ask(
            "\nEnter figure IDs separated by spaces (or press Enter for auto-select)",
            default=""
        )
    else:
        for i, f in enumerate(figures, 1):
            print(f"  {i:2}. {f['id']:<20} {f['name']}")
        raw = input("\nEnter figure IDs (space-separated, or Enter for auto): ").strip()

    if not raw:
        return None
    return raw.split()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Watch the panel argue.")
    parser.add_argument("question", nargs="?", help="Opening question")
    parser.add_argument("--panel", nargs="+", help="Figure IDs")
    parser.add_argument("--turns", type=int, default=5, help="Max turns (default: 5)")
    parser.add_argument("--size", type=int, default=3, help="Panel size if auto-selecting (default: 3)")
    parser.add_argument("--demo", action="store_true", help="Run a full auto conversation without user input")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SYMPOSIUM_API_KEY", ""),
        help="Anthropic API key (or set SYMPOSIUM_API_KEY env var)"
    )
    args = parser.parse_args()

    # ── API key validation ──────────────────────────────────────────────────
    api_key = args.api_key
    if not api_key:
        print("[ERROR] Anthropic API key required.")
        print("  Pass --api-key sk-ant-... or set SYMPOSIUM_API_KEY environment variable.")
        sys.exit(1)

    # ── Header ──────────────────────────────────────────────────────────────
    if RICH:
        console.print()
        console.print(Panel.fit(
            "[bold]Symposium[/bold]\nWatch history's greatest minds argue.",
            border_style="bright_black"
        ))
        console.print()
    else:
        print("\n=== Symposium ===\n")

    # ── Question ────────────────────────────────────────────────────────────
    if args.question:
        question = args.question
    else:
        if RICH:
            question = Prompt.ask("[bold]Opening question[/bold]")
        else:
            question = input("Opening question: ").strip()

    if not question.strip():
        print("Question cannot be empty.")
        sys.exit(1)

    # ── Panel ───────────────────────────────────────────────────────────────
    panel_ids = args.panel
    if not panel_ids:
        panel_ids = _pick_panel(api_key)   # None = auto

    # ── Start session ───────────────────────────────────────────────────────
    if RICH:
        with console.status("[dim]Convening the panel…[/dim]"):
            payload = {
                "question": question,
                "max_turns": args.turns,
                "panel_size": args.size,
            }
            if panel_ids:
                payload["figure_ids"] = panel_ids
            data = _post("/chat/start", payload, api_key)
    else:
        print("\nConvening the panel…")
        payload = {
            "question": question,
            "max_turns": args.turns,
            "panel_size": args.size,
        }
        if panel_ids:
            payload["figure_ids"] = panel_ids
        data = _post("/chat/start", payload, api_key)

    session_id = data["session_id"]
    speakers = {m["speaker_id"]: m["speaker_name"] for m in data["messages"]}

    # Print panel
    if RICH:
        panel_line = "  ".join(
            f"[{_colour(sid)}]{name}[/{_colour(sid)}]"
            for sid, name in speakers.items()
        )
        console.print(f"Panel: {panel_line}   [dim]session: {session_id}[/dim]\n")
    else:
        names = " · ".join(speakers.values())
        print(f"Panel: {names}  (session: {session_id})\n")

    # ── Opening round ───────────────────────────────────────────────────────
    _section("OPENING")
    for msg in data["messages"]:
        _render_message(msg)

    _token_line(data["token_usage"], data["turns_remaining"])

    if data["is_complete"]:
        _show_closing(data)
        return

    # Demo prompts — one per turn, designed to provoke good arguments
    _DEMO_PROMPTS = [
        "Do you three actually agree on anything?",
        "Which of you is most wrong?",
        "What would you each say to someone just starting their life?",
        "Final question: what do you each regret?",
        "Last word — what matters most?",
    ]
    _demo_idx = 0

    # ── Conversation loop ────────────────────────────────────────────────────
    while not data["is_complete"]:
        # User input
        if args.demo:
            user_msg = _DEMO_PROMPTS[_demo_idx % len(_DEMO_PROMPTS)]
            _demo_idx += 1
            if RICH:
                console.print(f"\n[bold white]>> You (auto):[/bold white] {user_msg}\n")
            else:
                print(f"\n>> You (auto): {user_msg}\n")
        else:
            try:
                if RICH:
                    user_msg = Prompt.ask("[bold white]You[/bold white]")
                else:
                    user_msg = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n(exiting)")
                break

        if not user_msg.strip():
            continue

        # Send turn
        if RICH:
            with console.status("[dim]Thinking…[/dim]"):
                data = _post(f"/chat/{session_id}", {"message": user_msg}, api_key)
        else:
            print("\nThinking…")
            data = _post(f"/chat/{session_id}", {"message": user_msg}, api_key)

        turn_label = f"TURN {data['turn']}"
        if data["is_complete"]:
            turn_label += "  (final)"
        _section(turn_label)

        for msg in data["messages"]:
            _render_message(msg)

        _token_line(data["token_usage"], data["turns_remaining"])

    # ── Closing ──────────────────────────────────────────────────────────────
    if data.get("is_complete"):
        _show_closing(data)


def _show_closing(data: dict):
    closing = [m for m in data["messages"] if m.get("is_closing")]
    if not closing:
        return
    _section("CLOSING STATEMENTS")
    for msg in closing:
        _render_message(msg)

    # Final token summary
    if RICH:
        usage = data["token_usage"]
        console.print()
        console.print(Panel.fit(
            f"Session complete\n"
            f"Total tokens: [bold]{usage['input_tokens']:,}[/bold] in / "
            f"[bold]{usage['output_tokens']:,}[/bold] out",
            border_style="dim"
        ))
    else:
        usage = data["token_usage"]
        print(f"\n── Session complete ──")
        print(f"Total tokens: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")


if __name__ == "__main__":
    main()
