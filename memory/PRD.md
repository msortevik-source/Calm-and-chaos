# Calm & Chaos — PRD

## Original problem statement
A familiar home for an overwhelmed but clever adult goblin. Emotional sequence: greeted → grounded → able to think. Feels like entering a familiar room. Low friction to thought. ONE main conversational engine connected to brain dumps, training, calendar, budget, food, patterns.

## Architecture
- React (CRA + craco) + Tailwind + Spectral/Manrope
- FastAPI + MongoDB (Motor)
- LLM: gpt-5.2 via Emergent universal key + emergentintegrations — ONE API call per user message (single-call architecture)
- Google Calendar OAuth read-only (single-user, working)
- Notion source-of-truth (read via integration token "Calm and chaos reader")
- PWA-ready (manifest.json + apple-touch-icon + standalone display)

## Personas
- Em — single user. No auth.

## Implemented
- v1 (2026-05-21): Home + Conversation + Brain dump + Training + Patterns + Google Calendar
- v1.1: Tone Constitution embedded; warmer palette; expanded BrainDump+Training schemas; Budget & Food; expanded Patterns
- v1.2: Data-aware conversation; Sunday letter from the room (cached per ISO week)
- v1.3 (2026-05-21):
  - **Single-call chat architecture** — history baked into composed user message, 1 LLM call per request (was 10). Latency 1.6–6.6s (was 10–20s). Cost ~$4–5/mo at heavy daily use (was ~$23/mo).
  - **Word-boundary regex** on context-keywords (e.g. "weekend" no longer triggers "week" data injection).
  - **Shared markdown renderer** (`/app/frontend/src/lib/markdown.jsx`) — bold/italic/inline-code in conversation, snapshots, letter.
  - **PWA-ready**: manifest.json, apple-touch-icon (180/192/512), theme-color, standalone display, safe-area-inset padding.
- Backend tests: 38/38 passing

## Backlog
- P1: One-tap "discuss this with the goblin" from any entry
- P1: Optional evening "before bed" check-in question
- P2: Total composed-prompt token cap; orphan user_msg cleanup on 502
- P2: Auto-stale letter cache after N hours
- P2: Letter regen for specific past weeks (?week_key param)
- P2: Custom domain after deploy
- Parking lot: Garmin/Strava auto-import, voice input, ambient goblin movement
