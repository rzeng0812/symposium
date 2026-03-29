# Symposium — Project Notes for Claude

## What This Is

Symposium is a FastAPI backend that convenes panels of historical figures to answer
questions. Each figure has a detailed soul config, a harm layer, copyright compliance
tracking, and post-generation output review. Not yet public.

---

## Pre-Launch Blockers (do not publish until resolved)

### 1. API Cost Architecture

Every conversation calls Claude multiple times:
- `law.py` — 1 call (harm classification)
- `panel.py` — 1 call (panel selection)
- `main.py` / `chat.py` — N calls (one per figure, in parallel)
- `quality.py` — N background calls (auto-scoring)
- `compliance.py` — N background calls (output review)

**A single `/ask` with 4 figures = ~10 Claude API calls.** A chat session compounds further.

Before going public, decide:
- User-supplied API keys (limits audience, removes billing risk)
- Platform pays + subscriptions/credits (requires pricing model)
- Vercel AI Gateway for unified billing + cost tracking

### 2. Copyright / Right of Publicity — ~30 Figures Not Production-Ready

`compliance.py` has a full `FIGURE_REGISTRY` with per-figure status. The `review_needed`
figures are **allowed through in dev mode** but flagged `production_ready: False`.

For commercial launch, `check_figure_eligibility()` must be hardened to **block**
`review_needed` figures unless explicitly cleared.

**Figures requiring legal clearance or removal before v1 commercial launch:**

| Figure | Issue |
|--------|-------|
| Einstein | Hebrew University holds publicity rights in some jurisdictions |
| Feynman | Feynman estate + Caltech hold commercial rights |
| Kahlo | Frida Kahlo Corporation — highly litigious, active enforcement |
| Jobs | Apple Inc. + Jobs estate manage likeness |
| Hawking | Hawking Estate + brand actively managed |
| Bowie | Troika Entertainment manages brand/likeness |
| Warhol | Andy Warhol Foundation — aggressive litigant |
| Picasso | Picasso Administration — commercial use blocked without clearance |
| Dali | Fundació Gala-Salvador Dalí holds image rights |
| Morrison | Toni Morrison estate recently established |
| Angelou | Maya Angelou estate actively manages rights |
| Sagan | Carl Sagan Institute + estate |
| Foucault | Estate + IMEC hold archival rights |
| Arendt | Hannah Arendt Literary Trust |
| Baldwin | James Baldwin Estate |
| de Beauvoir | Estate manages rights |
| Davis (Miles) | Estate actively manages likeness/brand |
| Chanel | Chanel S.A. holds trademark/brand rights |
| O'Keeffe | Georgia O'Keeffe Foundation — active enforcement |
| Lamarr | Hedy Lamarr estate |
| Wright F.L. | Frank Lloyd Wright Foundation — trademark active |
| von Braun | Sensitive: documented use of forced labor; content review needed |
| Engelbart | Doug Engelbart Institute manages legacy |
| Hopper | Estate / US Navy archives (lower risk) |
| Land | Estate has limited claims |
| Ritchie | Estate has limited claims |
| Sherlock Holmes | Conan Doyle Estate has been litigious — monitor |

**~70 figures are `public_domain` or `mostly_clear` and safe for v1.**

### 3. Disclaimer Enforcement

The disclaimer (Principle 1) is an API response field — nothing prevents a frontend
from hiding it. Before launch:
- ToS must require frontends to surface the disclaimer
- If we build our own frontend, the disclaimer must be visible on every response

### 4. Right of Publicity — Jurisdiction Variance

Even `public_domain` figures can have active estate claims in California and some
other jurisdictions for commercial use. If the product charges money, get a brief
legal review covering the ~70 "safe" figures before launch.

---

## What Is Already Built Well

- `law.py` — pre-generation harm classification (SAFE/UNSAFE)
- `compliance.py` — pre-generation eligibility check (living, copyright)
- `compliance.py` — post-generation output review (ideological harm, weaponizable,
  historical distortion) via Principle 7
- `PRINCIPLES.md` — 7 product principles documented and enforced in code
- No living people (Principle 5) — hardcoded block
- In-character refusal patterns on every figure (Principle 3)
- Quality auto-scoring in background (in_character, depth, soul_alignment)
- 101 figures with full soul configs, collision triggers, legacy awareness

---

## Architecture Notes

- Backend: FastAPI (`main.py`), Python 3.13
- Figure configs: `figures/configs.py` — all 101 figures, soul prompts, collision triggers
- Panel: `panel.py` — Claude-powered panel selection for max intellectual tension
- Chat: `chat.py` — multi-turn group conversation with speaker selection
- Storage: SQLite (`symposium.db`) — sessions, responses, quality scores, ratings
- Watch: `watch.py` — CLI tool to watch conversations in real time (Rich or plain)
- Tests: `tests/test_api.py` — requires live server (`uvicorn main:app --port 8765`)
- Model: `claude-opus-4-6` throughout (can be parameterized later)

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8765
python watch.py "Does free will exist?" --panel socrates nietzsche feynman
```
