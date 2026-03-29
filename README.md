# Symposium

**History's greatest minds, convened to answer your questions.**

Symposium assembles a panel of historical figures — philosophers, scientists, artists, mathematicians — and lets them argue with each other in real time. Each figure has a deep soul configuration built from their documented worldview, communication style, and known intellectual tensions with other figures.

---

## What makes this different

**Soul configs, not personas.** Each figure has a system prompt built from their actual documented positions — their epistemic method, their refusals, their collision triggers with specific other thinkers. Socrates never answers directly. Nietzsche attacks comfortable certainties. When they're in the same room, the tension is structural, not scripted.

**Collision triggers.** Every figure has a `collision_triggers` map — specific pairs where the intellectual conflict is documented and deep. Gentileschi and Foucault on power and the body. Nietzsche and Kant on the foundation of morality. The panel selection algorithm maximises these tensions for a given question.

**A real compliance layer.** Not an afterthought:
- Pre-generation harm classification (`law.py`)
- No living people, ever (Principle 5, hardcoded)
- Per-figure copyright and right-of-publicity registry
- Post-generation output review: ideological harm, weaponisable content, historical distortion
- Identity disclaimer on every single response

101 figures across 14 categories. Full principles documented in [`PRINCIPLES.md`](PRINCIPLES.md).

---

## Quickstart

**Requirements:** Python 3.13+, an [Anthropic API key](https://console.anthropic.com/)

```bash
git clone https://github.com/rzeng0812/symposium
cd symposium
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8765
```

Watch a live conversation:

```bash
python watch.py "Does free will exist?" --panel socrates nietzsche feynman
python watch.py "What is art for?"      --panel kahlo warhol da_vinci
python watch.py                          # interactive mode: pick question + panel
```

---

## API

```
GET  /figures                  List all 101 figures with role and soul signature
GET  /figures/{id}             Full figure profile (system prompt excluded)
POST /panel/suggest            Get a panel recommendation for a question
POST /ask                      Single-round: all figures answer in parallel
POST /chat/start               Start a multi-turn group conversation
POST /chat/{session_id}        Send a message, get 1–2 figure replies
GET  /chat/{session_id}        Full conversation history
GET  /chats                    Browse past sessions
GET  /history                  Browse past /ask sessions
GET  /quality                  Aggregate quality scores per figure
GET  /compliance               Copyright and eligibility status for all figures
```

### Panel suggestion

```bash
curl -X POST http://localhost:8765/panel/suggest \
  -H "Content-Type: application/json" \
  -d '{"question": "Is suffering necessary for great art?", "size": 4}'
```

### Start a conversation

```bash
# Start
curl -X POST http://localhost:8765/chat/start \
  -H "Content-Type: application/json" \
  -d '{"question": "What does justice require of us?", "panel_size": 3}'

# Continue (use session_id from above)
curl -X POST http://localhost:8765/chat/{session_id} \
  -H "Content-Type: application/json" \
  -d '{"message": "But what about those who have nothing to give?"}'
```

---

## The figures

101 figures across 14 categories:

Artists · Scientists · Philosophers · Mathematicians · Inventors · Computer Scientists · Polymaths · and more

Selected examples with their soul signatures:

| Figure | Role | Soul Signature |
|--------|------|----------------|
| Socrates | The Destabilizer | *Questions every premise, never answers directly* |
| Nietzsche | The Provocateur | *Explosive, poetic, attacks comfort* |
| Hypatia | The Geometer | *To teach is to make the mind free — and freedom has always had enemies.* |
| Rosalind Franklin | The Invisible Pioneer | *The data does not lie. The people who handle the data sometimes do.* |
| Alan Turing | The Codebreaker | *I asked whether machines could think. No one asked whether they'd treat me like one.* |
| Hannah Arendt | The Witness | *Evil needs no motive beyond the absence of thought.* |

Full roster: [`PANEL.md`](PANEL.md)

---

## Compliance

Every response includes a compliance block:

```json
{
  "compliance": {
    "disclaimer": "AI-generated interpretation. Not a real quote or verified historical position. Symposium reconstructs figures from documented sources — responses reflect informed interpretation, not the actual words or views of these individuals.",
    "status": "pass",
    "figures": {
      "socrates": { "copyright_status": "public_domain", "production_ready": true, "output_review_status": "pass" }
    }
  }
}
```

The disclaimer must be visible to users on every response.

---

## Self-hosting

Symposium is designed to be self-hosted. You need:

- An Anthropic API key (all inference runs through the Anthropic API)
- Python 3.13+ environment
- SQLite (included, no setup needed)

For production, swap `symposium.db` for Postgres by updating `storage.py`.

---

## Contributing

Contributions welcome — new figures, improved soul configs, bug fixes, alternative model support.

For new figures: follow the soul config structure in `figures/configs.py` and add a compliance entry in `compliance.py` before opening a PR. Figures without a compliance registry entry will be blocked at runtime.
