# Calm & Chaos — PRD

## Original problem statement
A familiar home for an overwhelmed but clever adult goblin. Emotional sequence: greeted → grounded → able to think. Feels like entering a familiar room. Low friction to thought. ONE main conversational engine connected to brain dumps, training, calendar, budget, food, patterns. Aesthetic: rainy Bergen forest + coffee + nervous system exhale.

## Architecture
- React (CRA + craco) + Tailwind + Spectral/Manrope fonts
- FastAPI + MongoDB (Motor)
- LLM: gpt-5.2 via Emergent universal key + emergentintegrations
- Google Calendar OAuth (single-user, working)
- Notion source-of-truth (read via "Calm and chaos reader" integration token)

## Personas
- Em — single user. No auth. The familiar room.

## Implemented
- 2026-05-21 v1: Home + Conversation + Brain dump + Training + Patterns + Google Calendar
- 2026-05-21 v1.1: Tone Constitution embedded; warmer palette; expanded schemas (BrainDump+Training); Budget & Food section; expanded Patterns
- 2026-05-21 v1.2:
  - **Data-aware conversation** — chat endpoint detects keywords (training/run/strength/brain dump/budget/spending/food/meals/week/month/look at my/...) and injects last-30-day summary into the goblin's system prompt. Verified: goblin now cites exact distances, weights, moods, tags, dates, wins of the day.
  - **Sunday letter from the room** — `/api/letter/current` generates GPT-5.2 weekly summary (cached by ISO week, force=true to regenerate). Letter page renders markdown bullets/bold; home page shows preview card. Voice is unmistakably goblin ("you act like a functional mammal", "your nervous system likes showing up more than thinking about showing up").
- Backend tests: 33/33 across iterations 1+2+3

## Backlog
- P1: One-tap "discuss this with the goblin" from any entry
- P1: Evening "before bed" check-in (optional, one quiet question)
- P2: Auto-stale letter cache after N hours (counts drift during the week)
- P2: Word-boundary regex on TIME_BROAD context-keywords (avoid 'weekend' triggering 'week')
- P2: Tighter Pydantic Literal validation; 404 on delete-miss
- P2: Letter regen for specific past weeks (?week_key param)
- Parking lot (per Em's Notion): Garmin/Strava auto-import, voice input, ambient goblin movement
