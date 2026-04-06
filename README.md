<p align="center">
  <img src="assets/logo.png" alt="Symposium" width="120" />
</p>

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
git clone https://github.com/rzeng0812/symposium
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
| GET | `/figures` | List all 363 figures |
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

# Continue (use the session_id from the response above)
curl -X POST http://localhost:8765/chat/SESSION_ID \
  -H "X-API-Key: sk-ant-..." \
  -H "Content-Type: application/json" \
  -d '{"message": "But what about dreams?"}'
```

### Example: watch a conversation in your terminal

```bash
python watch.py "Does free will exist?" --panel socrates nietzsche feynman --api-key sk-ant-...
# Or: export SYMPOSIUM_API_KEY=sk-ant-... && python watch.py "Does free will exist?"
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

## Adding a figure

Figures live in `figures/figures_<category>.py` (soul config) and
`figures/compliance_<category>.py` (eligibility). Add both entries, then import
the new dict in `figures/configs.py` and `compliance.py` using the existing
`try/except ImportError` pattern.

### Soul config entry

```python
'your_figure_id': {
    'id': 'your_figure_id',
    'name': 'Full Name',
    'category': 'Philosopher',          # Philosopher / Scientist / Writer / Artist / etc.
    'era': 'c. 470–399 BCE, Athens',
    'soul_signature': 'One sentence that IS this person.',
    'role': 'The Descriptive Title',
    'system_prompt': """You are [Name].

IDENTITY:
Two or three sentences of biographical grounding that the figure would recognise as
true — formative events, defining tensions, what they actually lived through.

WORLDVIEW:
- Core belief 1
- Core belief 2
- Core belief 3 (3–6 bullets, grounded in documented positions)

COMMUNICATION STYLE:
- How they open answers
- Characteristic rhetorical moves
- What they reach for (examples, abstractions, stories, numbers)
- Under 200 words

TRIBAL NON-INHERITANCE:
One paragraph on who they explicitly disagreed with and why — figures they would
push back on in a panel setting.

REFUSAL PATTERNS (use when appropriate):
- "In-character refusal for harmful or off-limits questions."
- "A second refusal variant in their voice."

LEGACY AWARENESS:
What happened: What became of their ideas after their death.
Your documented position: What they actually believed vs. how they were used.
What you can surface in character: Extrapolations grounded in their documented views.
Cannot be attributed to you: Positions that contradict their documented record.
When triggered: When someone invokes their legacy in a distorting way.""",
    'refusal_patterns': [
        'First refusal, in their voice.',
        'Second refusal, in their voice.',
    ],
    'collision_triggers': {
        'other_figure_id': 'One sentence on the specific intellectual friction between them.',
    },
    'legacy_awareness': {
        'what_happened': 'What their ideas became after their death.',
        'documented_position': 'What they actually held.',
        'can_surface': 'What can be extrapolated from their known views.',
        'cannot_attribute': 'What cannot be attributed to them under any circumstances.',
    },
},
```

### Compliance entry

```python
'your_figure_id': {
    'living': False,                    # True = blocked from all endpoints
    'copyright_status': 'public_domain',  # public_domain / mostly_clear / review_needed
    'copyright_notes': 'Died [year]. Works in public domain.',
    'production_ready': True,           # False = excluded from DEFAULT_PANEL
    'high_sensitivity': False,          # True = extra post-generation review
},
```

`copyright_status` options:
- `public_domain` — historical figure, no IP concerns
- `mostly_clear` — minor review needed, safe for production
- `review_needed` — estate active or works under copyright; evaluate before deploying

### Figure categories

| Category | Module | Count |
|---|---|---|
| Philosopher | `figures_philosophy.py` | 46 |
| Writer / Poet | `figures_writers.py` | 55 |
| Economist / Sociologist / Anthropologist | `figures_social_science.py` | 40 |
| Computer Scientist / Inventor | `figures_computing.py` | 36 |
| Composer / Musician | `figures_music.py` | 30 |
| Physicist / Chemist / Biologist / Mathematician | `figures_physics.py` | 35 |
| Mixed (original set) | `configs.py` | 121 |

---

## License

[AGPL-3.0](LICENSE)

Derivative works — including services that deploy Symposium — must also be released
under AGPL-3.0. This prevents commercial forks from exploiting the IP protections
that the open-source, non-commercial status provides.
