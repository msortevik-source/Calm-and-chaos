# Calm & Chaos — PRD

## Original problem statement
A familiar home for an overwhelmed but clever adult goblin. Greeted → grounded → able to think. Low friction to thought. ONE engine connected to brain dumps, training, calendar, budget, food, patterns.

## Architecture
- React (CRA + craco) + Tailwind + Spectral/Manrope
- FastAPI + MongoDB (Motor)
- LLM: gpt-5.2 via Emergent universal key + emergentintegrations — single-call per user message
- Google Calendar OAuth (single-user, working)
- Notion source-of-truth via integration token "Calm and chaos reader"
- PWA-ready: manifest.json + apple-touch-icon + standalone display + safe-area-inset

## Personas
- Em — single user. Android. No auth.

## Implemented
- v1: Home + Conversation + Brain dump + Training + Patterns + Google Calendar
- v1.1: Tone Constitution; warmer palette; expanded schemas; Budget & Food; expanded Patterns
- v1.2: Data-aware conversation; Sunday letter from the room (cached per ISO week)
- v1.3: Single-call chat (10→1 LLM calls); word-boundary regex; shared markdown renderer; PWA-ready
- v1.4 (2026-05-21):
  - **"Discuss with the goblin" buttons** on every entry (brain dump / training / budget / meal). Navigates to /conversation with the entry text pre-filled in the chat input. User chooses Send / Hard truth / Ground me / Organize. Single-room philosophy: every artifact in the room can become a conversation.
  - **Evening check-in** card on Home, visible only 21:00-02:00 local. One quiet question ("Anything circling before you close the laptop?") → saves a brain dump tagged `evening`. Dismissable per day via localStorage (`calm_chaos_evening_dismissed`).
- Backend tests: 38/38 passing (no backend changes in v1.4 — pure frontend)

## Backlog
- P2: Total composed-prompt token cap; orphan user_msg cleanup on 502
- P2: Auto-stale letter cache after N hours
- P2: Letter regen for specific past weeks (?week_key param)
- P2: Custom domain after deploy
- P2: Inline goblin response under "discuss this" (avoid the page navigation if user wants quick reply)
- Parking lot (per Em's Notion): Garmin/Strava, voice input, ambient goblin movement
