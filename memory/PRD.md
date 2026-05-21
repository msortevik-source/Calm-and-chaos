# Calm & Chaos — PRD

## Original problem statement
A familiar home for an overwhelmed but clever adult goblin. Emotional sequence: greeted → grounded → able to think. Feels like entering a familiar room. Low friction to thought. ONE main conversational engine that connects to brain dumps, training, calendar, budget, food, patterns. Aesthetic: rainy Bergen forest + coffee + nervous system exhale.

## Architecture
- React (CRA + craco) frontend, Tailwind, Spectral (heading) + Manrope (body)
- FastAPI backend, MongoDB (Motor)
- LLM: OpenAI gpt-5.2 via Emergent universal LLM key + emergentintegrations
- Google Calendar (read-only) OAuth — single-user
- Source of truth: Notion design doc + Behavior & Tone Constitution (8 principles embedded in goblin system prompt)

## Personas
- Single user (Em). No multi-user / no auth.

## Implemented
- 2026-05-21 v1: Home + Conversation + Brain dump + Training + Patterns + Google Calendar (OAuth working)
- 2026-05-21 v1.1:
  - **Tone Constitution** fully embedded in goblin system prompt (8 principles, mode-specific adaptive behavior)
  - **Warmer palette** (5-10% warmer; moss undertones, amber depth, warm-card surfaces; no void black)
  - **Brain Dump**: added `energy` (1-5), `mood` (heavy/meh/ok/good/flying), `tags`
  - **Training**: added `session_name`, `mood_before`, `mood_after`, `win_of_the_day`, `soreness_notes`
  - **Budget & Food** (new section): Budget (item/amount/category/date/notes + month totals + by-category aggregates); Meal Planning & Prep (meal/protein_source/prep_status/easy_quick/mood_after/notes/date)
  - **Patterns** expanded: mood drift, recurring brain-dump tags, regret-spending pattern, food↔mood correlation
- Backend tests: 28/28 passing (iteration_2.json)

## Backlog
- P1: Conversation engine aware of training / brain dump / budget / meal data (e.g. "how was my training this month?") — currently the goblin only has chat history memory
- P1: Goblin ambient presence (10% movement, 90% stillness) — parked per Notion
- P1: Sunday weekly "letter from the room" — quiet goblin-voice summary of the week
- P2: One-tap "discuss this with the goblin" from brain dump / training / budget entries
- P2: Garmin/Strava auto-import (parking lot)
- P2: Voice input (parking lot)
- P2: Notion sync (currently read-only via published URL — could be integration-token-based two-way)
- P2: Tighter Pydantic Literal validation on mode/category/mood/prep_status; 404 on delete-miss
