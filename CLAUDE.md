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
