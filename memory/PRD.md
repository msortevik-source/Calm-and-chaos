# Calm & Chaos — PRD

## Original problem statement
A familiar home for an overwhelmed but clever adult goblin. Emotional sequence: greeted → grounded → able to think. Feels like entering a familiar room, NOT a dashboard, NOT a therapist office, NOT a productivity tool. Low friction to thought. ONE main conversational engine that connects to brain dumps, training, calendar, patterns. Aesthetic: rainy Bergen forest + coffee + nervous system exhale (deep moss greens, charcoal, muted cream, soft amber).

## Architecture
- React (CRA + craco) frontend, Tailwind, Spectral (heading) + Manrope (body)
- FastAPI backend, MongoDB (Motor)
- LLM: OpenAI gpt-5.2 via Emergent universal LLM key + emergentintegrations
- Google Calendar (read-only) OAuth, single-user

## Personas
- Single user (the goblin's owner). No multi-user / no auth.

## Implemented (2026-05-21)
- Home: time-of-day greeting (4 windows), calendar snapshot, conversation snapshot, chat input with 4 modes (Send / Hard truth / Ground me / Organize my brain)
- Conversation: full chat history, multi-turn memory replay, clear
- Brain dump: timestamped entries, add/list/delete
- Training: weekly template (Mon/Wed/Fri), Run / Strength / Note logging, entries list
- Patterns: gentle observations across last 30 days from chat/braindump/training
- Google Calendar: OAuth + today/next-2-days events

## Backlog
- P1: Conversation aware of training & brain dump data (vector recall or summary injection)
- P1: Goblin ambient presence (10% movement, ASCII or subtle SVG) — parked
- P2: Brain dump → conversation (one-tap "discuss this")
- P2: Pattern thresholds tunable; more pattern types (training streaks, mode-frequency drift)
- P2: Calendar event creation (currently read-only)
- P2: Search across braindumps + chat
