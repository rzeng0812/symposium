# Symposium — Project Notes for Claude

## What This Is

Symposium is a FastAPI backend that convenes panels of historical figures to answer
questions. Each figure has a detailed soul config, a harm layer, copyright compliance
tracking, and post-generation output review.

**Status: private repo, iterating. Goes public once BYOK + frontend are done and checklist below is clear.**

---

## Publishing Decision — Open Source vs. Commercial

**Decision (2026-03-28): publish as open source under AGPL-3.0, not as a commercial product.**

### Why this resolves most blockers

**Copyright / Right of Publicity:** The legal risk for figures like Kahlo, Jobs,
Hawking, Warhol etc. is specifically about *commercial exploitation* of name and
likeness. Open source with no monetization is educational/research use — explicitly
tolerated by most estates. The ~30 `review_needed` figures are low risk in this context.

**API costs:** Each deployer uses their own Anthropic API key. We pay nothing.

**Remaining obligations (non-negotiable regardless of license):**
- No living people — Principle 5, hardcoded, never remove
- Harm layer — `law.py` must remain in the published codebase
- Disclaimer — `compliance.py` disclaimer must be in every API response;
  README must state frontends are required to surface it

### Why AGPL-3.0

AGPL requires all derivative works (including hosted services) to also be open source.
This prevents someone from forking the project, deploying it commercially, and
triggering the very IP concerns we're avoiding by going open source. MIT/Apache would
not provide this protection.

### License file

`LICENSE` — AGPL-3.0, added at root.

---

## Roadmap — Private → Public

### Current phase: private repo, iterating

**Before going public, in order:**

1. **BYOK backend wiring** — thread user-supplied API key per request
   - Accept `X-API-Key` header on all endpoints
   - Pass to `anthropic.Anthropic(api_key=...)` per request — never store or log
   - Validate key present, return clear error if missing

2. **Frontend** — Next.js on Vercel
   - Key input stored in `localStorage`, sent as header only
   - Figure browser + panel selection
   - Chat interface (main experience)
   - Single `/ask` mode

3. **LICENSE** — AGPL-3.0 (prevents commercial forks)

4. **README.md** — setup, API overview, deployment notice, disclaimer requirement

5. **Pre-publish checks** ✅ already clear:
   - `.env` in `.gitignore` ✅
   - No `ANTHROPIC_API_KEY` hardcoded in source ✅
   - No living people block (Principle 5) ✅
   - Harm layer (`law.py`) ✅
   - Output review (`compliance.py`) ✅
   - Disclaimer on every response (Principle 1) ✅

### Business model (decided)

- **Open source** under AGPL-3.0 — no commercial version
- **BYOK** — users supply their own Anthropic API key
- **Hosted website** — free, no charge
- **Self-hostable** — anyone can run it locally
- **No billing infrastructure needed**
- Optional: GitHub Sponsors if community grows

### Why private for now

Remaining concerns before public exposure:
- BYOK wiring not built yet — currently requires server-side API key
- No frontend — API-only product isn't accessible to general users
- No LICENSE or README — not ready for contributors

---

## Figures — Copyright Reference

For future decisions about adding figures or pursuing commercial deployment:

**`public_domain` or `mostly_clear` (~70 figures) — safe for all uses:**
Ancient/medieval figures, figures deceased before ~1930, most scientists and
philosophers. Full list in `compliance.py` FIGURE_REGISTRY.

**`review_needed` (~30 figures) — open source: low risk / commercial: needs clearance:**

| Figure | Estate / Rightsholder |
|--------|----------------------|
| Einstein | Hebrew University of Jerusalem |
| Feynman | Feynman estate + Caltech |
| Kahlo | Frida Kahlo Corporation (highly litigious) |
| Jobs | Apple Inc. + Jobs estate |
| Hawking | Stephen Hawking Estate |
| Bowie | Troika Entertainment |
| Warhol | Andy Warhol Foundation (aggressive litigant) |
| Picasso | Picasso Administration |
| Dali | Fundació Gala-Salvador Dalí |
| Morrison | Toni Morrison estate |
| Angelou | Maya Angelou estate |
| Sagan | Carl Sagan Institute + estate |
| Foucault | Estate + IMEC |
| Arendt | Hannah Arendt Literary Trust |
| Baldwin | James Baldwin Estate |
| de Beauvoir | Estate |
| Davis (Miles) | Miles Davis estate |
| Chanel | Chanel S.A. (trademark) |
| O'Keeffe | Georgia O'Keeffe Foundation |
| Lamarr | Hedy Lamarr estate |
| Wright F.L. | Frank Lloyd Wright Foundation |
| von Braun | Sensitive: forced labor history — content review needed regardless |
| Engelbart | Doug Engelbart Institute |
| Hopper | Estate / US Navy (lower risk) |
| Land | Estate (limited claims) |
| Ritchie | Estate (limited claims) |
| Sherlock Holmes | Conan Doyle Estate (litigious — monitor) |

**If we ever pursue commercial deployment:** `check_figure_eligibility()` in
`compliance.py` must be hardened to block `review_needed` figures unless explicitly
cleared. Currently they pass through with `production_ready: False` flagged.

---

## What Is Already Built

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

## Architecture

- Backend: FastAPI (`main.py`), Python 3.13
- Figure configs: `figures/configs.py` — all 101 figures, soul prompts, collision triggers
- Panel: `panel.py` — Claude-powered panel selection for max intellectual tension
- Chat: `chat.py` — multi-turn group conversation with speaker selection
- Storage: SQLite (`symposium.db`) — sessions, responses, quality scores, ratings
- Watch: `watch.py` — CLI tool to watch conversations in real time (Rich or plain)
- Tests: `tests/test_api.py` — requires live server (`uvicorn main:app --port 8765`)
- Model: `claude-opus-4-6` throughout

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8765
python watch.py "Does free will exist?" --panel socrates nietzsche feynman
```
