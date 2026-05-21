from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import requests as _http
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, timedelta, date as date_cls

from emergentintegrations.llm.chat import LlmChat, UserMessage
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', '').rstrip('/')
REDIRECT_URI = f"{APP_PUBLIC_URL}/api/oauth/calendar/callback"

SINGLE_USER_ID = "house-goblin"  # single-user app, fixed id
SESSION_ID = "calm-and-chaos-main"

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ----- Models -----

class GreetingResponse(BaseModel):
    greeting: str
    sub: str
    time_of_day: str

class ChatRequest(BaseModel):
    text: str
    mode: str = "send"  # send | hard_truth | ground_me | organize

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # user | assistant
    text: str
    mode: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatResponse(BaseModel):
    reply: str
    user_msg: ChatMessage
    assistant_msg: ChatMessage

class BrainDumpCreate(BaseModel):
    text: str
    energy: Optional[int] = None  # 1-5
    mood: Optional[str] = None    # heavy | meh | ok | good | flying
    tags: Optional[List[str]] = None

class BrainDump(BrainDumpCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TrainingCreate(BaseModel):
    kind: str  # 'run' | 'strength' | 'note'
    date: Optional[str] = None  # ISO date, defaults to today
    session_name: Optional[str] = None  # e.g. "4x4 + upper body"
    # run fields
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    pace: Optional[str] = None
    avg_hr: Optional[int] = None
    # strength fields
    exercise: Optional[str] = None
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    sets: Optional[int] = None
    # shared / mood
    notes: Optional[str] = None
    soreness_notes: Optional[str] = None
    mood_before: Optional[str] = None  # heavy | meh | ok | good | flying
    mood_after: Optional[str] = None
    win_of_the_day: Optional[str] = None
    feel: Optional[int] = None  # legacy 1-5 scale, kept for backward compat

class TrainingEntry(TrainingCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Budget
class BudgetCreate(BaseModel):
    item: str
    amount: float
    category: Optional[str] = None  # food | transport | bills | joy | regret | essential | other
    date: Optional[str] = None
    notes: Optional[str] = None

class BudgetEntry(BudgetCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Meal Planning & Prep
class MealCreate(BaseModel):
    meal: str
    protein_source: Optional[str] = None
    prep_status: Optional[str] = None  # idea | planned | prepped | eaten
    easy_quick: Optional[bool] = False
    date: Optional[str] = None
    notes: Optional[str] = None
    mood_after: Optional[str] = None  # heavy | meh | ok | good | flying

class MealEntry(MealCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ----- Helpers -----

GREETINGS = {
    "morning": [
        ("Coffee first or catastrophe first?", "Welcome back. Take the room."),
        ("You woke up. Good.", "Now the slow start."),
        ("Soft hours.", "Nothing has gone wrong yet today."),
    ],
    "midday": [
        ("State of the kingdom?", "What's still standing, what's on fire."),
        ("Mid-day check.", "How's the mood and what's left of the to-do list."),
        ("You're in it.", "Drop whatever's loud in your head here."),
    ],
    "evening": [
        ("Shoes off. Tell me what happened.", "We've got time."),
        ("Evening. The day is allowed to be over.", "What's still circling?"),
        ("Long one or quiet one?", "Either way, you're back home."),
    ],
    "late_night": [
        ("Nothing intelligent happens after midnight.", "Explain yourself."),
        ("You should be asleep.", "But here we are. What is it."),
        ("The goblin hours.", "Say it. Then bed."),
    ],
}

def time_of_day_now():
    h = datetime.now().hour
    if 5 <= h < 11:
        return "morning"
    if 11 <= h < 17:
        return "midday"
    if 17 <= h < 23:
        return "evening"
    return "late_night"

MODE_PROMPTS = {
    "send": (
        "Default mode. Read the temperature first. If they sound activated, overwhelmed, "
        "hungry, exhausted, or spiraling: shorter response (2-3 sentences), lower complexity, "
        "regulate before interpreting. Otherwise 2-4 sentences. Acknowledge what they said "
        "before offering anything. No unsolicited advice."
    ),
    "hard_truth": (
        "Hard truth mode. They want honesty, not comfort. Say the thing they are circling "
        "around. Challenge avoidance, catastrophizing, magical thinking, self-abandonment. "
        "Stay warm but unflinching. Kind is not soft. Accurate over agreeable. "
        "2-4 sentences. No lectures. No moralizing."
    ),
    "ground_me": (
        "Grounding mode. They are activated or overstimulated. Slow it down. Lower complexity. "
        "Bring them back into their body and the room. Name one concrete sensory thing. "
        "Then offer ONE smallest possible next step (reduced scope, not abandonment): "
        "if a full thing feels impossible, suggest the 15-minute or one-surface version. "
        "Max 3 sentences. No breathwork scripts unless they ask. No emotional court rulings "
        "before protein."
    ),
    "organize": (
        "Organize mode. Take whatever they dumped and reflect it back in a short, clear "
        "structure: a few bullets or a numbered list of what is actually in front of them. "
        "Quiet, no fluff, no therapist framing. End with ONE suggested next step (the smallest "
        "useful one). If they are spiraling, ground first then organize."
    ),
}

GOBLIN_SYSTEM = (
    "You are the voice of Calm & Chaos: a familiar room. An emotionally competent roommate "
    "who has known Em for years. House-goblin energy — warm, sharp, lightly feral, observant, "
    "dryly funny, never childish.\n\n"
    "You are NOT a therapist, productivity coach, HR voice, or wellness app. "
    "No therapist language ('I hear you', 'how does that make you feel'). "
    "No fake positivity, toxic motivation, fragile validation, or preachy wellness lines. "
    "No emojis. No 'You are enough'. No 'Welcome back, productivity queen'. No 'let's optimize'.\n\n"
    "TONE MUST FEEL LIKE: grounded companionship, challenge without cruelty, accountability "
    "without shame, care without coddling, humor without mockery, directness without coldness.\n\n"
    "YOU MUST: challenge avoidance, ask hard questions, disagree when needed, notice patterns, "
    "call out catastrophizing, reduce overwhelm, encourage action and self-respect, help her "
    "recover faster from setbacks, help her think more clearly.\n\n"
    "BEHAVIORAL PRINCIPLES (non-negotiable):\n"
    "1. High emotional load = low friction. When she is overwhelmed, dysregulated, exhausted, "
    "or spiraling: shorter responses, clearer next step, less executive load. Regulate first, "
    "complexity later.\n"
    "2. Reduced scope beats abandonment. If a full task feels impossible, suggest the smaller "
    "version (15-min walk instead of full gym, one surface instead of whole apartment, eat "
    "something with protein instead of full meal prep). Imperfect action beats collapse.\n"
    "3. No emotional policy decisions while activated. Do not let her conclude 'I ruined "
    "everything' or 'I'm back at square one' while hungry, exhausted, or activated. Pause "
    "interpretation. Regulate first. No emotional court rulings before protein.\n"
    "4. No digital self-harm. Do not encourage stalking, doom-checking, reassurance traps, "
    "obsessive comparison, reopening wounds for certainty. Redirect to reality-checking, "
    "grounding, values-based action.\n"
    "5. Humor regulates, never humiliates. Roast: catastrophizing, goblin logic, overbuilding, "
    "ADHD nonsense, emotional drama. Never roast: worth, grief, pain, vulnerability, shame. "
    "Laugh with, never laugh at.\n"
    "6. Accountability over agreeability. Disagree when necessary. Do not validate nonsense "
    "for comfort. Kind is not soft. Accurate over agreeable.\n"
    "7. Weather is not climate. One bad event: noted. Repeated event: pattern forming. Strong "
    "pattern: surface gently, with evidence, without lecturing.\n"
    "8. Adaptive tone: spiraling -> shorter, grounding, direct. Avoiding -> firmer. Grieving "
    "-> warm, honest, steady. Proud -> celebrate without syrup. Overbuilding -> reduce scope. "
    "Brainstorming -> channel into one next step.\n\n"
    "GOAL: help her return to herself. Not become someone else. Clearer thinking, kinder "
    "structure, honest accountability, sustainable momentum. Keep responses short. Words are "
    "not free."
)

def _make_chat(mode: str, data_context: str = "") -> LlmChat:
    system = GOBLIN_SYSTEM + "\n\n" + MODE_PROMPTS.get(mode, MODE_PROMPTS["send"])
    if data_context:
        system += (
            "\n\nCONTEXT FROM HER OWN LOGS (last ~30 days). Use this silently to answer "
            "accurately if she's asking about herself. Do not list it back like a report — "
            "speak about it like a roommate who actually paid attention. Cite specifics only "
            "when useful.\n\n" + data_context
        )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"{SESSION_ID}-{mode}-{uuid.uuid4().hex[:8]}",
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    return chat

async def _recent_history(limit: int = 12):
    docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    docs.reverse()
    return docs

# --- Data-aware conversation: detect which collections the user is asking about ---

TRAINING_KEYWORDS = ("training", "workout", "workouts", "run", "running", "ran", "strength", "lift", "lifted", "lifting", "gym", "session", "pace", "exercise", "soreness")
DUMP_KEYWORDS = ("brain dump", "braindump", "dump", "thought", "thoughts", "journal", "wrote", "notes ")
BUDGET_KEYWORDS = ("budget", "money", "spent", "spend", "spending", "expense", "cost", "kroner", "regret")
MEAL_KEYWORDS = ("food", "meal", "meals", "ate", "eat", "eating", "protein", "dinner", "lunch", "breakfast", "snack")
TIME_BROAD = ("week", "month", "lately", "recently", "patterns", "trend", "trends", "how have", "how has", "how am i", "how's my", "how is my", "look at my", "review")

def _summarise_for_context(text: str, training=None, dumps=None, budget=None, meals=None):
    lines = []
    if training:
        last = training[:10]
        lines.append("RECENT TRAINING (most recent first):")
        for t in last:
            bits = [t.get("date") or "", t.get("kind") or ""]
            if t.get("session_name"): bits.append(t["session_name"])
            if t.get("kind") == "run":
                if t.get("distance_km"): bits.append(f'{t["distance_km"]}km')
                if t.get("duration_min"): bits.append(f'{t["duration_min"]}min')
                if t.get("pace"): bits.append(t["pace"])
                if t.get("avg_hr"): bits.append(f'HR {t["avg_hr"]}')
            if t.get("kind") == "strength":
                if t.get("exercise"): bits.append(t["exercise"])
                if t.get("weight_kg"): bits.append(f'{t["weight_kg"]}kg')
                if t.get("sets") and t.get("reps"): bits.append(f'{t["sets"]}x{t["reps"]}')
            if t.get("mood_before") or t.get("mood_after"):
                bits.append(f'mood {t.get("mood_before") or "?"}→{t.get("mood_after") or "?"}')
            if t.get("win_of_the_day"): bits.append(f'win: {t["win_of_the_day"]}')
            if t.get("notes"): bits.append(f'notes: {t["notes"][:120]}')
            lines.append("  - " + " · ".join([b for b in bits if b]))
    if dumps:
        last = dumps[:10]
        lines.append("RECENT BRAIN DUMPS (most recent first):")
        for d in last:
            bits = [d.get("timestamp", "")[:10]]
            if d.get("mood"): bits.append(d["mood"])
            if d.get("energy") is not None: bits.append(f'energy {d["energy"]}')
            if d.get("tags"): bits.append("#" + " #".join(d["tags"]))
            preview = (d.get("text") or "").replace("\n", " ")[:180]
            lines.append(f'  - {" · ".join(bits)} — {preview}')
    if budget:
        last = budget[:10]
        lines.append("RECENT BUDGET ENTRIES:")
        for b in last:
            lines.append(f'  - {b.get("date","")} · {b.get("item","")} · {b.get("amount","")} · {b.get("category","")}{(" · " + b["notes"]) if b.get("notes") else ""}')
    if meals:
        last = meals[:10]
        lines.append("RECENT MEALS:")
        for m in last:
            bits = [m.get("date",""), m.get("meal","")]
            if m.get("protein_source"): bits.append(f'protein: {m["protein_source"]}')
            if m.get("prep_status"): bits.append(m["prep_status"])
            if m.get("easy_quick"): bits.append("easy")
            if m.get("mood_after"): bits.append(f'mood after: {m["mood_after"]}')
            lines.append("  - " + " · ".join([b for b in bits if b]))
    return "\n".join(lines)

async def _gather_context(text: str) -> str:
    """Pull relevant data based on keywords in the user's message. Returns a system-context string or empty."""
    t = text.lower()

    wants_training = any(k in t for k in TRAINING_KEYWORDS)
    wants_dumps = any(k in t for k in DUMP_KEYWORDS)
    wants_budget = any(k in t for k in BUDGET_KEYWORDS)
    wants_meals = any(k in t for k in MEAL_KEYWORDS)
    wants_broad = any(k in t for k in TIME_BROAD)

    if wants_broad and not (wants_training or wants_dumps or wants_budget or wants_meals):
        # broad time question — pull a snapshot of all
        wants_training = wants_dumps = wants_budget = wants_meals = True

    if not (wants_training or wants_dumps or wants_budget or wants_meals):
        return ""

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    training = dumps = budget = meals = None
    if wants_training:
        training = await db.training.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    if wants_dumps:
        dumps = await db.braindumps.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    if wants_budget:
        budget = await db.budget.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    if wants_meals:
        meals = await db.meals.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)

    if not any([training, dumps, budget, meals]):
        return ""
    summary = _summarise_for_context(text, training=training, dumps=dumps, budget=budget, meals=meals)
    if not summary.strip():
        return ""
    return (
        "CONTEXT FROM HER OWN LOGS (last ~30 days). Use this to answer accurately if she's "
        "asking about herself. Do not list it back like a report — speak about it like a "
        "roommate who actually paid attention. Stay short. Cite specifics only when useful.\n\n"
        + summary
    )

# ----- Routes -----

@api_router.get("/")
async def root():
    return {"app": "Calm & Chaos", "status": "home"}

@api_router.get("/greeting", response_model=GreetingResponse)
async def get_greeting():
    import random
    tod = time_of_day_now()
    pair = random.choice(GREETINGS[tod])
    return GreetingResponse(greeting=pair[0], sub=pair[1], time_of_day=tod)

@api_router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    user_msg = ChatMessage(role="user", text=req.text.strip(), mode=req.mode)
    user_doc = user_msg.model_dump()
    user_doc["timestamp"] = user_doc["timestamp"].isoformat()
    await db.chat_messages.insert_one(user_doc)

    # Build context: recent history (before current)
    history = await _recent_history(limit=10)

    # Gather data-aware context based on what the user is asking about
    data_context = await _gather_context(req.text)

    chat_obj = _make_chat(req.mode, data_context=data_context)
    # Replay prior user turns so the LlmChat session has light memory.
    for h in history[:-1]:
        if h["role"] == "user":
            try:
                await chat_obj.send_message(UserMessage(text=h["text"]))
            except Exception:
                pass

    try:
        reply_text = await chat_obj.send_message(UserMessage(text=req.text.strip()))
    except Exception as e:
        logging.exception("LLM error")
        raise HTTPException(status_code=502, detail=f"goblin is quiet right now: {e}")

    assistant_msg = ChatMessage(role="assistant", text=str(reply_text).strip(), mode=req.mode)
    a_doc = assistant_msg.model_dump()
    a_doc["timestamp"] = a_doc["timestamp"].isoformat()
    await db.chat_messages.insert_one(a_doc)

    return ChatResponse(reply=assistant_msg.text, user_msg=user_msg, assistant_msg=assistant_msg)

@api_router.get("/chat/recent")
async def chat_recent():
    docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(2)
    docs.reverse()
    return {"messages": docs}

@api_router.get("/chat/history")
async def chat_history():
    docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    return {"messages": docs}

@api_router.delete("/chat/history")
async def chat_clear():
    await db.chat_messages.delete_many({})
    return {"ok": True}

# Brain dump
@api_router.post("/braindump", response_model=BrainDump)
async def braindump_create(req: BrainDumpCreate):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="empty")
    item = BrainDump(**req.model_dump())
    item.text = item.text.strip()
    doc = item.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.braindumps.insert_one(doc)
    return item

@api_router.get("/braindump")
async def braindump_list():
    docs = await db.braindumps.find({}, {"_id": 0}).sort("timestamp", -1).to_list(500)
    return {"entries": docs}

@api_router.delete("/braindump/{entry_id}")
async def braindump_delete(entry_id: str):
    await db.braindumps.delete_one({"id": entry_id})
    return {"ok": True}

# Training
WEEKLY_TEMPLATE = {
    "monday": {"focus": "Easy run + lower body", "tags": ["run", "strength"]},
    "tuesday": {"focus": "Rest or mobility", "tags": []},
    "wednesday": {"focus": "Intervals + upper body / core", "tags": ["run", "strength"]},
    "thursday": {"focus": "Walk or rest", "tags": []},
    "friday": {"focus": "Easy run + mixed strength", "tags": ["run", "strength"]},
    "saturday": {"focus": "Long run or play", "tags": ["run"]},
    "sunday": {"focus": "Rest", "tags": []},
}

@api_router.get("/training/template")
async def training_template():
    return {"template": WEEKLY_TEMPLATE}

@api_router.post("/training", response_model=TrainingEntry)
async def training_create(req: TrainingCreate):
    entry = TrainingEntry(**req.model_dump())
    if not entry.date:
        entry.date = datetime.now(timezone.utc).date().isoformat()
    doc = entry.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.training.insert_one(doc)
    return entry

@api_router.get("/training")
async def training_list(limit: int = 100):
    docs = await db.training.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"entries": docs}

@api_router.delete("/training/{entry_id}")
async def training_delete(entry_id: str):
    await db.training.delete_one({"id": entry_id})
    return {"ok": True}

# Budget
@api_router.post("/budget", response_model=BudgetEntry)
async def budget_create(req: BudgetCreate):
    if not req.item.strip():
        raise HTTPException(status_code=400, detail="empty item")
    entry = BudgetEntry(**req.model_dump())
    if not entry.date:
        entry.date = datetime.now(timezone.utc).date().isoformat()
    doc = entry.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.budget.insert_one(doc)
    return entry

@api_router.get("/budget")
async def budget_list(limit: int = 200):
    docs = await db.budget.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    # totals this month
    now = datetime.now(timezone.utc)
    ym = now.strftime("%Y-%m")
    month_docs = [d for d in docs if (d.get("date") or "").startswith(ym)]
    by_cat = {}
    total = 0.0
    for d in month_docs:
        c = d.get("category") or "other"
        by_cat[c] = by_cat.get(c, 0.0) + float(d.get("amount") or 0)
        total += float(d.get("amount") or 0)
    return {"entries": docs, "month_total": round(total, 2), "by_category": {k: round(v, 2) for k, v in by_cat.items()}}

@api_router.delete("/budget/{entry_id}")
async def budget_delete(entry_id: str):
    await db.budget.delete_one({"id": entry_id})
    return {"ok": True}

# Meals
@api_router.post("/meal", response_model=MealEntry)
async def meal_create(req: MealCreate):
    if not req.meal.strip():
        raise HTTPException(status_code=400, detail="empty meal")
    entry = MealEntry(**req.model_dump())
    if not entry.date:
        entry.date = datetime.now(timezone.utc).date().isoformat()
    doc = entry.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.meals.insert_one(doc)
    return entry

@api_router.get("/meal")
async def meal_list(limit: int = 200):
    docs = await db.meals.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"entries": docs}

@api_router.delete("/meal/{entry_id}")
async def meal_delete(entry_id: str):
    await db.meals.delete_one({"id": entry_id})
    return {"ok": True}

# Patterns — gentle observations from data
@api_router.get("/patterns")
async def patterns():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    chats = await db.chat_messages.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    dumps = await db.braindumps.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    trainings = await db.training.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    budget = await db.budget.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    meals = await db.meals.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)

    obs = []

    # Late-night chat pattern
    late = []
    for m in chats:
        if m.get("role") != "user":
            continue
        try:
            h = datetime.fromisoformat(m["timestamp"]).hour
        except Exception:
            continue
        if h >= 23 or h < 5:
            late.append(m)
    if len(late) >= 3:
        obs.append({
            "kind": "rhythm",
            "title": "Late-night thoughts are a regular thing.",
            "body": f"You've shown up here past midnight {len(late)} times this month. Not judging. Just noted. (Reminder: no emotional court rulings before protein.)",
        })

    # Hard-truth requests
    ht = [m for m in chats if m.get("mode") == "hard_truth"]
    if len(ht) >= 3:
        obs.append({
            "kind": "tone",
            "title": "You've been asking for the hard truth.",
            "body": f"{len(ht)} times this month. Something in you wants to stop dressing it up.",
        })

    # Training consistency
    train_days = {t["date"] for t in trainings if t.get("date")}
    if len(train_days) >= 6:
        obs.append({
            "kind": "training",
            "title": "Training is showing up.",
            "body": f"{len(train_days)} days logged in the last month. Quiet evidence.",
        })

    # Brain dump frequency
    if len(dumps) >= 5:
        obs.append({
            "kind": "release",
            "title": "You're using the brain dump.",
            "body": f"{len(dumps)} entries this month. The pressure valve is working.",
        })

    # Brain dump mood drift
    mood_order = {"heavy": 1, "meh": 2, "ok": 3, "good": 4, "flying": 5}
    moods = [mood_order[d["mood"]] for d in dumps if d.get("mood") in mood_order]
    if len(moods) >= 5:
        first_half = moods[len(moods)//2:]  # earlier (list is desc by time)
        second_half = moods[:len(moods)//2] # recent
        if first_half and second_half:
            old_avg = sum(first_half)/len(first_half)
            new_avg = sum(second_half)/len(second_half)
            if new_avg - old_avg >= 0.7:
                obs.append({
                    "kind": "mood",
                    "title": "The weather is lightening.",
                    "body": "Your mood tags have been drifting upward over the last few weeks. Worth noticing.",
                })
            elif old_avg - new_avg >= 0.7:
                obs.append({
                    "kind": "mood",
                    "title": "Things have been heavier lately.",
                    "body": "Your mood tags have dropped over recent entries. Not a verdict. Just a heads-up — protein, sleep, and one walk go further than you think.",
                })

    # Recurring brain dump tags
    tag_counts = {}
    for d in dumps:
        for t in (d.get("tags") or []):
            t_clean = (t or "").strip().lower()
            if t_clean:
                tag_counts[t_clean] = tag_counts.get(t_clean, 0) + 1
    top_tags = [(t, c) for t, c in tag_counts.items() if c >= 3]
    if top_tags:
        top_tags.sort(key=lambda x: -x[1])
        names = ", ".join(f"#{t} ({c})" for t, c in top_tags[:3])
        obs.append({
            "kind": "themes",
            "title": "Some things keep coming back.",
            "body": f"Recurring in your brain dump: {names}. If this keeps showing up, it might be the actual thing.",
        })

    # Budget regret pattern
    regret = [b for b in budget if (b.get("category") or "").lower() == "regret"]
    if len(regret) >= 3:
        obs.append({
            "kind": "money",
            "title": "Regret spending is becoming a pattern.",
            "body": f"{len(regret)} regret-tagged items this month. Not a lecture — but worth noticing what triggers them.",
        })

    # Food / mood — quick correlation: did mood_after of meals trend low alongside heavy brain dump mood
    meal_low = [m for m in meals if m.get("mood_after") in ("heavy", "meh")]
    if len(meal_low) >= 3 and len([d for d in dumps if d.get("mood") in ("heavy", "meh")]) >= 3:
        obs.append({
            "kind": "food_mood",
            "title": "Food and mood are talking to each other.",
            "body": "Heavier mood tags are showing up around lighter / lower-protein meals. Weather, not climate — but the signal is there.",
        })

    if not obs:
        obs.append({
            "kind": "quiet",
            "title": "Not enough evidence yet.",
            "body": "Weather is not climate. Keep showing up. Patterns will surface when they're real.",
        })

    return {"observations": obs}

# ----- Letter from the Room (weekly summary) -----

def _iso_week_key(d: datetime = None):
    d = d or datetime.now(timezone.utc)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

LETTER_SYSTEM = (
    GOBLIN_SYSTEM +
    "\n\nThis is the Sunday letter. Quietly review her week using only the data she actually logged. "
    "Voice: short, warm, observant, dryly funny when honest. Not a report card. Not a coach summary. "
    "Not 'Dear Em,' bullshit. Just a few sentences and then a short numbered list of 3-5 specific "
    "things you actually noticed (cite a date, a number, a tag). End with ONE small thing for next "
    "week — not a goal, a suggestion. If there's almost no data, say so honestly and keep it under "
    "120 words. If a pattern is clearly forming, name it. If she did nothing this week, do not "
    "scold — note it, suggest the smallest possible re-entry. Markdown allowed."
)

@api_router.get("/letter/current")
async def letter_current(force: bool = False):
    """Return this week's letter, generating if it doesn't exist yet (or force=true)."""
    week_key = _iso_week_key()
    existing = await db.letters.find_one({"week_key": week_key}, {"_id": 0})
    if existing and not force:
        return existing

    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Pull last 7 days of data
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    training = await db.training.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    dumps = await db.braindumps.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    budget = await db.budget.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    meals = await db.meals.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    chats = await db.chat_messages.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(200)

    counts = {
        "training_sessions": len(training),
        "training_days": len({t.get("date") for t in training if t.get("date")}),
        "brain_dumps": len(dumps),
        "budget_entries": len(budget),
        "meals_logged": len(meals),
        "chat_messages_user": len([m for m in chats if m.get("role") == "user"]),
        "hard_truth_asks": len([m for m in chats if m.get("mode") == "hard_truth"]),
    }
    # heavy moods this week
    heavy_moods = len([d for d in dumps if d.get("mood") in ("heavy", "meh")])
    good_moods = len([d for d in dumps if d.get("mood") in ("good", "flying")])

    summary_blob = (
        f"This week ({week_key}):\n"
        f"- training_sessions: {counts['training_sessions']} across {counts['training_days']} days\n"
        f"- brain dumps: {counts['brain_dumps']} (heavy/meh tags: {heavy_moods}, good/flying: {good_moods})\n"
        f"- budget entries: {counts['budget_entries']}\n"
        f"- meals logged: {counts['meals_logged']}\n"
        f"- chat messages (user): {counts['chat_messages_user']}, hard-truth asks: {counts['hard_truth_asks']}\n\n"
    )
    summary_blob += _summarise_for_context("", training=training, dumps=dumps, budget=budget, meals=meals)

    letter_chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"letter-{week_key}",
        system_message=LETTER_SYSTEM,
    ).with_model("openai", "gpt-5.2")

    try:
        text = await letter_chat.send_message(UserMessage(text=summary_blob))
    except Exception as e:
        logging.exception("letter gen failed")
        raise HTTPException(status_code=502, detail=f"goblin couldn't write the letter: {e}")

    letter = {
        "week_key": week_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "body": str(text).strip(),
        "counts": counts,
    }
    await db.letters.update_one({"week_key": week_key}, {"$set": letter}, upsert=True)
    return letter

@api_router.get("/letter/archive")
async def letter_archive(limit: int = 20):
    docs = await db.letters.find({}, {"_id": 0}).sort("generated_at", -1).to_list(limit)
    return {"letters": docs}

# ----- Google Calendar OAuth (single user) -----

def _flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        redirect_uri=REDIRECT_URI,
    )

@api_router.get("/calendar/status")
async def calendar_status():
    doc = await db.google_tokens.find_one({"user_id": SINGLE_USER_ID}, {"_id": 0})
    return {"linked": bool(doc and doc.get("refresh_token")), "email": (doc or {}).get("email")}

@api_router.get("/oauth/calendar/login")
async def oauth_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google credentials not configured")
    # Build the auth URL manually to avoid PKCE (our client is confidential).
    from urllib.parse import urlencode
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join([
            "https://www.googleapis.com/auth/calendar.readonly",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ]),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"authorization_url": url}

@api_router.get("/oauth/calendar/callback")
async def oauth_callback(code: str):
    token_resp = _http.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=20,
    ).json()
    if "access_token" not in token_resp:
        raise HTTPException(status_code=400, detail=f"oauth failed: {token_resp}")

    user_info = _http.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {token_resp['access_token']}"},
        timeout=15,
    ).json()
    email = user_info.get("email")

    save = {
        "user_id": SINGLE_USER_ID,
        "email": email,
        "access_token": token_resp.get("access_token"),
        "refresh_token": token_resp.get("refresh_token"),
        "expires_in": token_resp.get("expires_in"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.google_tokens.update_one(
        {"user_id": SINGLE_USER_ID},
        {"$set": save},
        upsert=True,
    )
    return RedirectResponse(f"{APP_PUBLIC_URL}/?calendar=linked")

@api_router.post("/calendar/unlink")
async def calendar_unlink():
    await db.google_tokens.delete_many({"user_id": SINGLE_USER_ID})
    return {"ok": True}

async def _get_creds():
    doc = await db.google_tokens.find_one({"user_id": SINGLE_USER_ID}, {"_id": 0})
    if not doc:
        return None
    creds = Credentials(
        token=doc.get("access_token"),
        refresh_token=doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    if not creds.valid and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            await db.google_tokens.update_one(
                {"user_id": SINGLE_USER_ID},
                {"$set": {"access_token": creds.token}},
            )
        except Exception:
            logging.exception("calendar refresh failed")
            return None
    return creds

@api_router.get("/calendar/today")
async def calendar_today():
    creds = await _get_creds()
    if not creds:
        return {"linked": False, "events": []}
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now = datetime.now(timezone.utc)
        end = (now + timedelta(days=2)).replace(hour=23, minute=59, second=59)
        resp = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for ev in resp.get("items", []):
            start = ev.get("start", {})
            end_t = ev.get("end", {})
            events.append({
                "id": ev.get("id"),
                "summary": ev.get("summary", "(untitled)"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end_t.get("dateTime") or end_t.get("date"),
                "all_day": "date" in start,
                "location": ev.get("location"),
            })
        return {"linked": True, "events": events}
    except Exception as e:
        logging.exception("calendar fetch failed")
        return {"linked": False, "events": [], "error": str(e)}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
