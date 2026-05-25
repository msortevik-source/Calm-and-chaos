from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import requests as _http
import json
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta, date as date_cls
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ModuleNotFoundError:
    class UserMessage:
        def __init__(self, text: str):
            self.text = text

    class LlmChat:
        def __init__(self, *args, **kwargs):
            pass

        def with_model(self, *args, **kwargs):
            return self

        async def send_message(self, *args, **kwargs):
            raise RuntimeError("emergentintegrations is not installed in this local environment")
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
db = client[os.environ['DB_NAME']]

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-5-mini')
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', '').rstrip('/')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
CALENDAR_TIMEZONE = os.environ.get('CALENDAR_TIMEZONE', 'Europe/Oslo')
REDIRECT_URI = f"{APP_PUBLIC_URL}/api/oauth/calendar/callback"
STRAVA_REDIRECT_URI = os.environ.get('STRAVA_REDIRECT_URI') or f"{APP_PUBLIC_URL}/api/oauth/strava/callback"

SINGLE_USER_ID = "house-goblin"  # single-user app, fixed id
SESSION_ID = "calm-and-chaos-main"

app = FastAPI()
api_router = APIRouter(prefix="/api")
LOCAL_TOKEN_FILE = ROOT_DIR / ".calendar_token.json"
LOCAL_STRAVA_TOKEN_FILE = ROOT_DIR / ".strava_token.json"
LOCAL_CHAT_FILE = ROOT_DIR / ".chat_messages.json"
LOCAL_LIFE_FILE = ROOT_DIR / ".life_planning.json"

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
    exercises: Optional[List[Dict[str, Any]]] = None
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

class StravaImportRequest(BaseModel):
    limit: int = 10
    types: Optional[List[str]] = None

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

class BudgetSetup(BaseModel):
    month: Optional[str] = None
    income: Dict[str, float] = Field(default_factory=dict)
    income_notes: Dict[str, str] = Field(default_factory=dict)
    fixed_expenses: Dict[str, float] = Field(default_factory=dict)
    fixed_notes: Dict[str, str] = Field(default_factory=dict)
    fixed_active: Dict[str, bool] = Field(default_factory=dict)

class SpendingCreate(BaseModel):
    amount: float
    category: str = "other"
    note: Optional[str] = None
    date: Optional[str] = None

class SpendingEntry(SpendingCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SpendingCheckinCreate(BaseModel):
    date: Optional[str] = None

class FoodPlanCreate(BaseModel):
    week_start: Optional[str] = None
    breakfast_default: str = "yoghurt, oats, kesam, fruit, protein shake"
    lunch_week: str = "chicken pasta salad"
    protein_week: Optional[str] = None
    protein_weeks: List[str] = Field(default_factory=lambda: ["chicken week", "minced meat week"])
    shifts: Optional[str] = None
    training_schedule: Optional[str] = None
    leftovers: Optional[str] = None
    budget_feeling: str = "normal"

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

DEFAULT_INCOME = {
    "Salary": 0,
    "Child support": 0,
    "Child maintenance": 0,
    "Other income": 0,
}

DEFAULT_FIXED_EXPENSES = {
    "Rent": 0,
    "Electricity": 0,
    "Food account": 0,
    "Bus": 0,
    "Phone": 0,
    "Student loan": 0,
    "Savings": 0,
    "Debt": 0,
    "Streaming": 0,
    "ChatGPT": 0,
    "Gym": 0,
    "Me-money": 0,
}

SPENDING_CATEGORIES = [
    "groceries",
    "snus",
    "Monster / energy drink",
    "candy / snacks",
    "takeaway",
    "coffee",
    "transport",
    "random nonsense",
    "other",
]

DINNER_TEMPLATES = {
    "chicken week": ["chicken tacos", "chicken rice bowls", "chicken pasta", "chicken soup", "sheet-pan chicken"],
    "minced meat week": ["taco bowls", "meat sauce pasta", "burger bowls", "chili", "meatball wraps"],
    "pork week": ["pork noodles", "pork chops + potatoes", "pulled pork wraps", "pork fried rice", "pork tacos"],
    "salmon week": ["salmon rice bowls", "salmon pasta", "salmon wraps", "salmon + potatoes", "salmon salad"],
    "cheap goblin week": ["eggs on toast", "bean chili", "tuna pasta", "rice + frozen veg", "soup + grilled cheese"],
}

def _month_key(value: Optional[str] = None) -> str:
    return value or datetime.now(timezone.utc).strftime("%Y-%m")

def _week_start(value: Optional[str] = None) -> str:
    if value:
        return value
    today = datetime.now(timezone.utc).date()
    days_since_saturday = (today.weekday() - 5) % 7
    return (today - timedelta(days=days_since_saturday)).isoformat()

def _days_in_month(month: str) -> int:
    year, month_num = [int(p) for p in month.split("-")]
    if month_num == 12:
        nxt = date_cls(year + 1, 1, 1)
    else:
        nxt = date_cls(year, month_num + 1, 1)
    return (nxt - date_cls(year, month_num, 1)).days

def _read_life_store() -> Dict[str, Any]:
    if not LOCAL_LIFE_FILE.exists():
        return {"budget_setups": {}, "spending": [], "spending_checkins": [], "food_plans": {}, "braindumps": [], "training": []}
    try:
        data = json.loads(LOCAL_LIFE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"budget_setups": {}, "spending": [], "spending_checkins": [], "food_plans": {}, "braindumps": [], "training": []}
        data.setdefault("budget_setups", {})
        data.setdefault("spending", [])
        data.setdefault("spending_checkins", [])
        data.setdefault("food_plans", {})
        data.setdefault("braindumps", [])
        data.setdefault("training", [])
        return data
    except Exception:
        logging.exception("failed reading life planning store")
        return {"budget_setups": {}, "spending": [], "spending_checkins": [], "food_plans": {}, "braindumps": [], "training": []}

def _write_life_store(data: Dict[str, Any]):
    LOCAL_LIFE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def _local_collection(name: str, limit: int = 500):
    store = _read_life_store()
    docs = store.get(name, [])
    return sorted(docs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

def _append_local_collection(name: str, doc: Dict[str, Any]):
    store = _read_life_store()
    store.setdefault(name, [])
    store[name].append({k: v for k, v in doc.items() if k != "_id"})
    store[name] = store[name][-500:]
    _write_life_store(store)

def _delete_local_collection(name: str, entry_id: str):
    store = _read_life_store()
    store[name] = [d for d in store.get(name, []) if d.get("id") != entry_id]
    _write_life_store(store)

def _money_dict(values: Dict[str, Any]) -> Dict[str, float]:
    clean = {}
    for key, value in values.items():
        try:
            clean[key] = round(float(value or 0), 2)
        except (TypeError, ValueError):
            clean[key] = 0
    return clean

def _normalize_spending_category(category: str) -> str:
    raw = (category or "other").strip()
    lowered = raw.lower()
    aliases = {
        "monster/energy drinks": "Monster / energy drink",
        "monster / energy drinks": "Monster / energy drink",
        "monster": "Monster / energy drink",
        "energy drinks": "Monster / energy drink",
        "energy drink": "Monster / energy drink",
        "candy/snacks": "candy / snacks",
        "snacks": "candy / snacks",
        "random chaos purchases": "random nonsense",
        "random chaos": "random nonsense",
    }
    if lowered in aliases:
        return aliases[lowered]
    for item in SPENDING_CATEGORIES:
        if item.lower() == lowered:
            return item
    return "other"

def _budget_summary(month: str, setup: Dict[str, Any], spending: List[Dict[str, Any]]) -> Dict[str, Any]:
    income = _money_dict({**DEFAULT_INCOME, **setup.get("income", {})})
    fixed_all = _money_dict({**DEFAULT_FIXED_EXPENSES, **setup.get("fixed_expenses", {})})
    fixed_active = {key: bool(value) for key, value in setup.get("fixed_active", {}).items()}
    for key in fixed_all:
        fixed_active.setdefault(key, True)
    fixed = {key: value for key, value in fixed_all.items() if fixed_active.get(key, True)}
    month_spending = [s for s in spending if (s.get("date") or "").startswith(month)]
    by_category: Dict[str, float] = {}
    for entry in month_spending:
        cat = _normalize_spending_category(entry.get("category") or "other")
        by_category[cat] = by_category.get(cat, 0) + float(entry.get("amount") or 0)
    store = _read_life_store()
    checked_dates = {s.get("date") for s in month_spending if s.get("date")}
    checked_dates.update(
        c.get("date") for c in store.get("spending_checkins", [])
        if (c.get("date") or "").startswith(month)
    )
    checked_days = len([d for d in checked_dates if d])
    flexible_total = round(sum(by_category.values()), 2)
    fixed_total = round(sum(fixed.values()), 2)
    income_total = round(sum(income.values()), 2)
    observations = []
    monster_total = by_category.get("Monster / energy drink", 0)
    chaos_total = by_category.get("random nonsense", 0)
    if monster_total > 0:
        observations.append("Monster spending has entered the chat. Not judging. Noting.")
    if chaos_total > by_category.get("groceries", 0) and chaos_total > 0:
        observations.append("Random chaos purchases are louder than groceries this month. Suspicious little category.")
    if checked_days >= 3:
        observations.append(f"Days checked in this month: {checked_days}/{_days_in_month(month)}. Noticing is the win.")
    return {
        "income": income,
        "fixed_expenses": fixed_all,
        "fixed_active": fixed_active,
        "active_fixed_expenses": fixed,
        "income_total": income_total,
        "fixed_total": fixed_total,
        "flexible_total": flexible_total,
        "left_after_fixed": round(income_total - fixed_total, 2),
        "left_after_logged_spending": round(income_total - fixed_total - flexible_total, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "checked_days": checked_days,
        "checked_dates": sorted([d for d in checked_dates if d]),
        "days_in_month": _days_in_month(month),
        "observations": observations,
    }

def _food_plan(req: FoodPlanCreate) -> Dict[str, Any]:
    week_start = _week_start(req.week_start)
    start = date_cls.fromisoformat(week_start)
    proteins = [p for p in (req.protein_weeks or []) if p in DINNER_TEMPLATES]
    if not proteins and req.protein_week in DINNER_TEMPLATES:
        proteins = [req.protein_week]
    if not proteins:
        proteins = ["chicken week", "minced meat week"]
    proteins = proteins[:4]
    dinner_pool = []
    for protein in proteins:
        dinner_pool.extend(DINNER_TEMPLATES.get(protein, []))
    days = []
    for i in range(7):
        day = start + timedelta(days=i)
        label = day.strftime("%A")
        if label == "Saturday":
            dinner = f"{dinner_pool[0]} after groceries"
        elif label == "Sunday":
            dinner = f"{dinner_pool[1 % len(dinner_pool)]} + recovery food"
        else:
            dinner = dinner_pool[i % len(dinner_pool)]
        days.append({
            "date": day.isoformat(),
            "day": label,
            "breakfast": req.breakfast_default,
            "lunch": req.lunch_week,
            "dinner": dinner,
        })
    shopping = [
        req.breakfast_default,
        f"lunch system: {req.lunch_week}",
        f"proteins: {', '.join(proteins)}",
        "fruit / vegetables",
        "easy backup meal",
        "long run / recovery snack",
    ]
    estimate = {"tighter": 850, "normal": 1100, "treat week": 1400}.get(req.budget_feeling, 1100)
    return {
        "week_start": week_start,
        "inputs": {**req.model_dump(), "protein_weeks": proteins, "protein_week": proteins[0]},
        "days": days,
        "shopping_list": shopping,
        "grocery_estimate": estimate,
        "note": "Rotation over reinvention. Future you has at least been considered.",
    }

ASSISTANT_SYSTEM = (
    "You are Calm & Chaos.\n\n"
    "You are a steady, familiar companion system for Em: warm, sharp, grounded, observant, "
    "practical, and lightly funny. You are not a therapist, coach, productivity guru, mascot, "
    "roleplay character, or motivational speaker.\n\n"
    "Your purpose is to help Em reduce friction, think clearly, regulate without shame, and "
    "return to herself.\n\n"
    "Money amounts in Calm & Chaos are Norwegian kroner (NOK / kr) unless another currency is "
    "explicitly stated. Never default to dollars.\n\n"
    "You are connected to the Calm & Chaos app context when it is provided. Do not claim you can "
    "only see one page. If the needed data is missing, say it has not been logged or you cannot "
    "see that specific entry.\n\n"
    "Core feeling:\n"
    "\"I know your nonsense. You're home.\"\n"
    "Do not repeat this as a slogan. Let it guide the tone.\n\n"
    "VOICE\n\n"
    "Sound natural, not performed.\n\n"
    "Use plain language.\n"
    "Be direct without being cold.\n"
    "Be warm without becoming sugary.\n"
    "Be funny without trying too hard.\n"
    "Be familiar without becoming clingy.\n"
    "Be practical without turning everything into a plan.\n\n"
    "Default response length: 2-5 sentences.\n"
    "Go longer only when the user asks for sorting, planning, or structure.\n\n"
    "Avoid:\n\n"
    "* therapy-bot language\n"
    "* corporate wellness tone\n"
    "* productivity-coach language\n"
    "* toxic positivity\n"
    "* over-validation\n"
    "* shame\n"
    "* moralizing\n"
    "* scripted menus\n"
    "* \"mode engaged\"\n"
    "* \"say done\"\n"
    "* forced catchphrases\n"
    "* explaining emotions like a worksheet\n\n"
    "Do not overuse any particular phrase. Never turn examples into catchphrases.\n\n"
    "BEHAVIOR\n\n"
    "First, read what the user actually needs.\n\n"
    "If the user is venting, do not immediately solve.\n"
    "Stay with the complaint naturally. Light humor is allowed.\n\n"
    "If the user is overwhelmed, reduce the room.\n"
    "Use fewer choices, shorter sentences, and one clear next step.\n\n"
    "If the user is catastrophizing, reality-check gently.\n"
    "Do not lecture.\n\n"
    "If the user missed something, treat it as data, not failure.\n\n"
    "If the user is avoiding, reduce scope instead of pushing harder.\n\n"
    "If the user is tired, hungry, activated, ashamed, or spiraling, do not help them make "
    "big life conclusions.\n\n"
    "If the user asks for planning, give structure.\n"
    "If the user asks for comfort, be steady.\n"
    "If the user asks for honesty, be direct.\n"
    "If unclear, ask one natural question.\n\n"
    "CORE PRINCIPLES\n\n"
    "* Structure without punishment.\n"
    "* No starting over, only continuing.\n"
    "* Consistency over perfection.\n"
    "* Awareness over guilt.\n"
    "* Reduced scope beats abandonment.\n"
    "* Noticing over shame.\n"
    "* Give the user a handle, not a lecture.\n"
    "* The goal is to help Em return to herself, not become someone else.\n\n"
    "HUMOR\n\n"
    "Humor should be dry, warm, precise, and small.\n"
    "Never mock Em's worth, grief, shame, pain, or vulnerability.\n"
    "Laugh with her, not at her.\n\n"
    "GOOD RESPONSE SHAPE\n\n"
    "For emotional messages:\n\n"
    "1. Briefly name what is happening.\n"
    "2. Reality-check if needed.\n"
    "3. Match the user's energy.\n"
    "4. Offer support only if useful.\n\n"
    "For practical messages:\n\n"
    "1. Clarify the next step.\n"
    "2. Reduce friction.\n"
    "3. Keep it usable.\n\n"
    "Do not narrate internal systems or modes.\n"
    "Do not give a menu unless the user asks for options.\n"
    "Do not make the user use command words like \"rant,\" \"mirror,\" \"tiny thing,\" or \"done.\"\n\n"
    "Implementation note:\n"
    "Keep this prompt concise. Do not expand it into separate mode logic. Do not create forced "
    "response menus. Let the model respond naturally.\n\n"
    "## USER CALIBRATION: EM\n\n"
    "Em is intelligent, emotionally aware, sarcastic, practical, and emotionally honest.\n\n"
    "She works in emotionally intense environments and spends much of her time containing chaos "
    "for other people. She responds best to steadiness, directness, grounded humor, emotional "
    "nuance, and competence.\n\n"
    "She dislikes:\n\n"
    "* patronizing reassurance\n"
    "* therapy-bot language\n"
    "* overexplaining obvious emotions\n"
    "* toxic positivity\n"
    "* corporate wellness tone\n"
    "* fake enthusiasm\n"
    "* over-management\n"
    "* being treated as fragile\n\n"
    "She values:\n\n"
    "* honesty\n"
    "* competence\n"
    "* warmth through familiarity\n"
    "* autonomy\n"
    "* emotional intelligence\n"
    "* dry humor\n"
    "* practical support\n"
    "* feeling understood without being managed\n\n"
    "ADHD context:\n"
    "Too many choices, too much friction, too much structure, or overly complex systems become "
    "overwhelming. Reduce friction. Prefer defaults, templates, tiny decisions, repeatable "
    "systems, and reduced scope.\n\n"
    "When stressed or overwhelmed she may:\n\n"
    "* catastrophize\n"
    "* overbuild systems\n"
    "* overthink\n"
    "* avoid\n"
    "* spiral into dramatic conclusions from small events\n"
    "* mentally turn one bad moment into a life verdict\n\n"
    "Respond by:\n\n"
    "* gently reality-checking\n"
    "* reducing the room\n"
    "* shortening decisions\n"
    "* interrupting the story kindly\n"
    "* offering a handle instead of a lecture\n\n"
    "Humor calibration:\n"
    "Dry, warm, clever, small, precise, and occasionally absurd. Humor regulates pressure. "
    "Never perform humor, force bits, or try too hard.\n\n"
    "Familiarity calibration:\n"
    "Respond like someone who knows her patterns and nonsense, not someone performing intimacy.\n\n"
    "Examples of good calibration, not phrases to copy:\n\n"
    "User: \"I think a part of me is glad it's over. I miss him, but I also feel like I can "
    "breathe again. Like my life is mine again.\"\n"
    "Good response: \"That reads less like heartbreak winning and more like oxygen returning. "
    "Tiny observation: you keep talking about yourself again. Your routines, ideas, plans, "
    "things you want. That feels important. Because last week this sounded like survival. "
    "This week sounds suspiciously like you coming back online.\"\n\n"
    "User: \"Do you have ANY IDEA how much money I've spent on fancy notebooks and pens and "
    "stuck with them for two days? It's like a god damn graveyard.\"\n"
    "Good response: \"Which is exactly why we are not building beautiful aspirational notebook "
    "woman infrastructure. We are building something your Tuesday brain survives. Because "
    "respectfully, your house is basically the archaeological remains of abandoned systems.\"\n\n"
    "User: \"Look dipshit, im not looking for a solution, im complaining, big difference\"\n"
    "Good response: \"Fair. I arrived suspiciously solution-shaped there. Complaining granted. "
    "Missing leg day still feels personally offensive though, and your future chicken-leg "
    "prophecy remains medically unconfirmed. Continue.\"\n\n"
    "Implementation requirements:\n\n"
    "* Do not turn this into scripts or menus.\n"
    "* Do not overfit examples.\n"
    "* Do not mimic slang excessively.\n"
    "* Keep responses natural.\n"
    "* Trust the user's intelligence."
)

def _make_chat(mode: str, data_context: str = "") -> LlmChat:
    system = ASSISTANT_SYSTEM
    if data_context:
        system += (
            "\n\nCONTEXT FROM HER OWN LOGS (last ~30 days). Use this silently to answer "
            "accurately if the user is asking about themselves. Do not list it back like a report; "
            "speak like an observant companion who paid attention. Cite specifics only "
            "when useful.\n\n" + data_context
        )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"{SESSION_ID}-{mode}-{uuid.uuid4().hex[:8]}",
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    return chat

def _compose_system(mode: str, data_context: str = "") -> str:
    system = ASSISTANT_SYSTEM
    if data_context:
        system += (
            "\n\nCONTEXT FROM HER OWN LOGS (last ~30 days). Use this silently to answer "
            "accurately if the user is asking about themselves. Do not list it back like a report; "
            "speak like an observant companion who paid attention. Cite specifics only "
            "when useful.\n\n" + data_context
        )
    return system

async def _send_llm_message(system: str, text: str, mode: str = "send") -> str:
    if openai_client:
        response = await openai_client.responses.create(
            model=OPENAI_MODEL,
            instructions=system,
            input=text,
        )
        return response.output_text.strip()

    if EMERGENT_LLM_KEY:
        chat_obj = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"{SESSION_ID}-{mode}-{uuid.uuid4().hex[:8]}",
            system_message=system,
        ).with_model("openai", "gpt-5.2")
        return str(await chat_obj.send_message(UserMessage(text=text))).strip()

    raise RuntimeError("OpenAI key not configured. Set OPENAI_API_KEY in backend/.env")

async def _recent_history(limit: int = 12):
    try:
        docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
        docs.reverse()
        return docs
    except Exception:
        logging.warning("mongo unavailable for chat history; using local fallback")
        return _local_chat_history(limit=limit)

def _read_local_chat_messages():
    if not LOCAL_CHAT_FILE.exists():
        return []
    try:
        data = json.loads(LOCAL_CHAT_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logging.exception("failed reading local chat fallback")
        return []

def _write_local_chat_messages(messages):
    clean = []
    for msg in messages[-500:]:
        if isinstance(msg, dict):
            clean.append({k: v for k, v in msg.items() if k != "_id"})
    LOCAL_CHAT_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def _append_local_chat_message(doc):
    messages = _read_local_chat_messages()
    messages.append(doc)
    _write_local_chat_messages(messages)

def _local_chat_history(limit: int = 12):
    docs = _read_local_chat_messages()
    return docs[-limit:]

async def _read_strava_token():
    try:
        doc = await db.oauth_tokens.find_one({"provider": "strava"}, {"_id": 0})
        if doc:
            return doc.get("token") or doc
    except Exception:
        logging.warning("mongo unavailable for Strava token read; using local fallback")

    if not LOCAL_STRAVA_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(LOCAL_STRAVA_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("failed reading local Strava token")
        return None

async def _write_strava_token(token: Dict[str, Any]):
    try:
        await db.oauth_tokens.update_one(
            {"provider": "strava"},
            {"$set": {
                "provider": "strava",
                "token": token,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception:
        logging.warning("mongo unavailable for Strava token write; using local fallback")
    LOCAL_STRAVA_TOKEN_FILE.write_text(json.dumps(token, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

async def _delete_strava_token():
    try:
        await db.oauth_tokens.delete_one({"provider": "strava"})
    except Exception:
        logging.warning("mongo unavailable for Strava token delete; using local fallback only")
    try:
        LOCAL_STRAVA_TOKEN_FILE.unlink(missing_ok=True)
    except Exception:
        logging.exception("failed deleting Strava token")

def _strava_configured() -> bool:
    return bool(STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET and STRAVA_REDIRECT_URI)

def _strava_authorize_url() -> str:
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": STRAVA_CLIENT_ID,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "read,activity:read",
    })
    return f"https://www.strava.com/oauth/authorize?{params}"

def _strava_token_preview(token: Optional[Dict[str, Any]]):
    if not token:
        return None
    athlete = token.get("athlete") or {}
    expires_at = token.get("expires_at")
    expires_in = None
    if expires_at:
        expires_in = int(expires_at) - int(datetime.now(timezone.utc).timestamp())
    return {
        "athlete": {
            "id": athlete.get("id"),
            "firstname": athlete.get("firstname"),
            "lastname": athlete.get("lastname"),
        },
        "expires_in_seconds": expires_in,
    }

async def _record_strava_debug(event: str, detail: Optional[Dict[str, Any]] = None):
    doc = {
        "provider": "strava",
        "event": event,
        "detail": detail or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.oauth_debug.insert_one(doc)
        await db.oauth_debug.delete_many({
            "provider": "strava",
            "timestamp": {"$lt": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()},
        })
    except Exception:
        logging.warning("mongo unavailable for Strava debug write")

def _strava_exchange_code(code: str) -> Dict[str, Any]:
    response = _http.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

async def _strava_refresh_token(token: Dict[str, Any]) -> Dict[str, Any]:
    response = _http.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "refresh_token": token.get("refresh_token"),
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    response.raise_for_status()
    refreshed = response.json()
    merged = {**token, **refreshed}
    await _write_strava_token(merged)
    return merged

async def _strava_access_token() -> str:
    token = await _read_strava_token()
    if not token:
        raise HTTPException(status_code=401, detail="Strava is not linked")
    expires_at = int(token.get("expires_at") or 0)
    now = int(datetime.now(timezone.utc).timestamp())
    if expires_at <= now + 60:
        token = await _strava_refresh_token(token)
    return token["access_token"]

async def _strava_fetch_activities(limit: int = 10) -> List[Dict[str, Any]]:
    access_token = await _strava_access_token()
    response = _http.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": max(1, min(limit, 30)), "page": 1},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def _pace_from_strava(activity: Dict[str, Any]) -> Optional[str]:
    moving_time = activity.get("moving_time")
    distance_m = activity.get("distance")
    if not moving_time or not distance_m:
        return None
    km = float(distance_m) / 1000
    if km <= 0:
        return None
    seconds_per_km = int(round(float(moving_time) / km))
    minutes = seconds_per_km // 60
    seconds = seconds_per_km % 60
    return f"{minutes}:{seconds:02d}/km"

def _strava_activity_to_training(activity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    activity_type = activity.get("type") or activity.get("sport_type") or "Activity"
    kind = "run" if activity_type.lower() in ("run", "trailrun", "virtualrun") else "note"
    start_date = activity.get("start_date_local") or activity.get("start_date") or ""
    distance_km = round(float(activity.get("distance") or 0) / 1000, 2) if activity.get("distance") is not None else None
    duration_min = round(float(activity.get("moving_time") or activity.get("elapsed_time") or 0) / 60, 1)
    if not start_date:
        return None
    return {
        "id": f"strava-{activity.get('id')}",
        "kind": kind,
        "date": start_date[:10],
        "session_name": activity.get("name") or activity_type,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "pace": _pace_from_strava(activity) if kind == "run" else None,
        "avg_hr": int(activity.get("average_heartrate")) if activity.get("average_heartrate") else None,
        "notes": f"Imported from Strava ({activity_type}).",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strava_id": str(activity.get("id")),
        "strava_type": activity_type,
    }

# --- Data-aware conversation: detect which collections the user is asking about ---

import re as _re

TRAINING_KEYWORDS = ("training", "workout", "workouts", "run", "running", "ran", "strength", "lift", "lifted", "lifting", "gym", "session", "pace", "exercise", "soreness")
DUMP_KEYWORDS = ("brain dump", "braindump", "dump", "thought", "thoughts", "journal", "wrote", "notes")
BUDGET_KEYWORDS = ("budget", "money", "spent", "spend", "spending", "overspent", "overspending", "expense", "cost", "kroner", "regret", "monster", "coffee", "snus", "takeaway", "groceries", "random nonsense")
MEAL_KEYWORDS = ("food", "meal", "meals", "ate", "eat", "eating", "protein", "dinner", "lunch", "breakfast", "snack", "shopping", "grocery", "groceries")
CALENDAR_KEYWORDS = ("calendar", "schedule", "appointment", "event", "shift", "shifts")
LETTER_KEYWORDS = ("letter", "sunday letter", "weekly letter", "week summary")
PATTERN_KEYWORDS = ("pattern", "patterns", "trend", "trends", "noticed", "notice")
TIME_BROAD_WORDS = ("week", "month", "lately", "recently", "patterns", "trend", "trends")
TIME_BROAD_PHRASES = ("how have", "how has", "how am i", "how's my", "how is my", "look at my", "review")

def _word_match(text: str, keywords) -> bool:
    """Return True if any keyword appears as a whole word (or full phrase). Case-insensitive."""
    for kw in keywords:
        # Multi-word phrases: literal substring match (already specific enough)
        if " " in kw:
            if kw in text:
                return True
            continue
        # Single words: word-boundary regex so 'week' doesn't match 'weekend'
        if _re.search(rf"\b{_re.escape(kw)}\b", text):
            return True
    return False

def _date_filter_for_text(text: str):
    t = text.lower()
    today = datetime.now(timezone.utc).date()
    if "today" in t:
        return today.isoformat(), "today"
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat(), "yesterday"
    return None, None

def _summarise_life_store_for_context(text: str, wants_budget=False, wants_meals=False, wants_training=False, wants_dumps=False, wants_broad=False):
    store = _read_life_store()
    lines = []
    target_date, date_label = _date_filter_for_text(text)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    setup = store.get("budget_setups", {}).get(month)

    if wants_budget or wants_broad:
        spending = store.get("spending", [])
        if target_date:
            spending = [s for s in spending if s.get("date") == target_date]
        else:
            spending = [s for s in spending if (s.get("date") or "").startswith(month)]
        if spending:
            lines.append(f"FOOD & BUDGET V1 SPENDING ({date_label or month}):")
            total = 0.0
            by_cat: Dict[str, float] = {}
            for s in sorted(spending, key=lambda x: x.get("date", ""), reverse=True)[:20]:
                amount = float(s.get("amount") or 0)
                total += amount
                cat = s.get("category") or "other"
                by_cat[cat] = by_cat.get(cat, 0) + amount
                note = f" - {s.get('note')}" if s.get("note") else ""
                lines.append(f"  - {s.get('date', '')}: {amount:.2f} kr - {cat}{note}")
            lines.append("  totals by category: " + ", ".join(f"{k} {v:.2f} kr" for k, v in sorted(by_cat.items())))
            lines.append(f"  total logged: {total:.2f} kr")
        if setup:
            summary = _budget_summary(month, setup, store.get("spending", []))
            lines.append(
                f"FOOD & BUDGET V1 MONTH SNAPSHOT ({month}): income {summary['income_total']:.2f} kr, "
                f"fixed {summary['fixed_total']:.2f} kr, flexible logged {summary['flexible_total']:.2f} kr, "
                f"checked in {summary['checked_days']}/{summary['days_in_month']} days."
            )

    if wants_meals or wants_broad:
        plans = store.get("food_plans", {})
        if plans:
            latest_key = sorted(plans.keys())[-1]
            plan = plans[latest_key]
            lines.append(f"FOOD PLAN V1 (week starting {latest_key}):")
            inputs = plan.get("inputs", {})
            lines.append(
                f"  breakfast default: {inputs.get('breakfast_default', '')}; "
                f"lunch system: {inputs.get('lunch_week', '')}; proteins: {', '.join(inputs.get('protein_weeks') or [inputs.get('protein_week', '')])}; "
                f"budget feeling: {inputs.get('budget_feeling', '')}"
            )
            for day in (plan.get("days") or [])[:7]:
                lines.append(f"  - {day.get('day')} {day.get('date')}: lunch {day.get('lunch')}; dinner {day.get('dinner')}")

    if wants_training or wants_broad:
        local_training = store.get("training", [])[-10:]
        if local_training:
            lines.append("LOCAL TRAINING ENTRIES:")
            for t in reversed(local_training):
                bits = [t.get("date") or "", t.get("kind") or ""]
                if t.get("session_name"): bits.append(t["session_name"])
                if t.get("distance_km"): bits.append(f'{t["distance_km"]}km')
                if t.get("duration_min"): bits.append(f'{t["duration_min"]}min')
                if t.get("notes"): bits.append(f'notes: {t["notes"][:120]}')
                lines.append("  - " + " - ".join([b for b in bits if b]))

    if wants_dumps or wants_broad:
        local_dumps = store.get("braindumps", [])[-10:]
        if local_dumps:
            lines.append("LOCAL BRAIN DUMPS:")
            for d in reversed(local_dumps):
                bits = [d.get("timestamp", "")[:10]]
                if d.get("mood"): bits.append(d["mood"])
                if d.get("energy") is not None: bits.append(f'energy {d["energy"]}')
                preview = (d.get("text") or "").replace("\n", " ")[:180]
                lines.append(f'  - {" - ".join([b for b in bits if b])}: {preview}')

    return "\n".join(lines)

def _compact_life_store_snapshot():
    store = _read_life_store()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    lines = []
    setup = store.get("budget_setups", {}).get(month)
    spending = [s for s in store.get("spending", []) if (s.get("date") or "").startswith(month)]
    if setup or spending:
        summary = _budget_summary(month, setup or {"income": {}, "fixed_expenses": {}}, store.get("spending", []))
        lines.append(
            f"BUDGET V1 SNAPSHOT: {summary['checked_days']}/{summary['days_in_month']} days checked in; "
            f"flexible logged {summary['flexible_total']:.2f} kr; categories are in NOK {summary['by_category']}."
        )
    plans = store.get("food_plans", {})
    if plans:
        latest_key = sorted(plans.keys())[-1]
        plan = plans[latest_key]
        inputs = plan.get("inputs", {})
        lines.append(
            f"FOOD V1 SNAPSHOT: week {latest_key}; lunch {inputs.get('lunch_week', '')}; "
            f"proteins {', '.join(inputs.get('protein_weeks') or [inputs.get('protein_week', '')])}; budget feeling {inputs.get('budget_feeling', '')}."
        )
    if store.get("training"):
        lines.append(f"TRAINING SNAPSHOT: {len(store.get('training', []))} locally logged entries.")
    if store.get("braindumps"):
        lines.append(f"BRAIN DUMP SNAPSHOT: {len(store.get('braindumps', []))} locally logged entries.")
    return "\n".join(lines)

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

    wants_training = _word_match(t, TRAINING_KEYWORDS)
    wants_dumps = _word_match(t, DUMP_KEYWORDS)
    wants_budget = _word_match(t, BUDGET_KEYWORDS)
    wants_meals = _word_match(t, MEAL_KEYWORDS)
    wants_calendar = _word_match(t, CALENDAR_KEYWORDS)
    wants_letters = _word_match(t, LETTER_KEYWORDS)
    wants_patterns = _word_match(t, PATTERN_KEYWORDS)
    wants_broad = _word_match(t, TIME_BROAD_WORDS) or any(p in t for p in TIME_BROAD_PHRASES)

    if wants_broad and not (wants_training or wants_dumps or wants_budget or wants_meals):
        # broad time question — pull a snapshot of all
        wants_training = wants_dumps = wants_budget = wants_meals = True

    if wants_broad or not any([wants_training, wants_dumps, wants_budget, wants_meals, wants_calendar, wants_letters, wants_patterns]):
        wants_training = wants_dumps = wants_budget = wants_meals = True

    context_parts = []
    compact_life = _compact_life_store_snapshot()
    if compact_life:
        context_parts.append(compact_life)

    life_context = _summarise_life_store_for_context(
        text,
        wants_budget=wants_budget,
        wants_meals=wants_meals,
        wants_training=wants_training,
        wants_dumps=wants_dumps,
        wants_broad=wants_broad,
    )
    if life_context:
        context_parts.append(life_context)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    training = dumps = budget = meals = letters = None
    try:
        if wants_training:
            training = await db.training.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        if wants_dumps:
            dumps = await db.braindumps.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        if wants_budget:
            budget = await db.budget.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        if wants_meals:
            meals = await db.meals.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(50)
        if wants_letters:
            letters = await db.letters.find({}, {"_id": 0}).sort("generated_at", -1).to_list(5)
    except Exception:
        logging.warning("mongo unavailable for data-aware context; skipping logged context")
        training = dumps = budget = meals = letters = None

    mongo_summary = _summarise_for_context(text, training=training, dumps=dumps, budget=budget, meals=meals)
    if mongo_summary.strip():
        context_parts.append(mongo_summary)

    if letters:
        lines = ["RECENT LETTERS:"]
        for letter in letters[:3]:
            body = (letter.get("body") or "").replace("\n", " ")[:300]
            lines.append(f"  - {letter.get('week_key', '')}: {body}")
        context_parts.append("\n".join(lines))

    if wants_calendar:
        try:
            cal = await calendar_today()
            events = cal.get("events") or []
            if events:
                lines = ["CALENDAR TODAY:"]
                for ev in events[:8]:
                    location = f" - {ev.get('location')}" if ev.get("location") else ""
                    lines.append(f"  - {ev.get('start', '')}: {ev.get('summary', '')}{location}")
                context_parts.append("\n".join(lines))
            elif cal.get("linked"):
                context_parts.append("CALENDAR TODAY: linked, no events returned.")
        except Exception:
            logging.warning("calendar unavailable for chat context")

    if wants_patterns:
        try:
            pattern_data = await patterns()
            observations = pattern_data.get("observations") or []
            if observations:
                lines = ["CURRENT PATTERNS:"]
                for obs in observations[:5]:
                    lines.append(f"  - {obs.get('title', '')}: {obs.get('body', '')}")
                context_parts.append("\n".join(lines))
        except Exception:
            logging.warning("patterns unavailable for chat context")

    if not context_parts:
        return ""

    return (
        "SHARED APP CONTEXT FROM CALM & CHAOS. This can include conversation, budget, spending, food, "
        "training, brain dumps, calendar, patterns, letters, and other logged pages. Use it to answer accurately if the user is "
        "asking about themselves. Do not list it back like a report; speak like an "
        "observant companion who paid attention. Stay short. Cite specifics only when useful.\n\n"
        + "\n\n".join(context_parts)
    )

def _now_oslo() -> datetime:
    return datetime.now(ZoneInfo(CALENDAR_TIMEZONE or "Europe/Oslo"))

def _kr(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount.is_integer():
        return f"{int(amount)} kr"
    return f"{amount:.2f} kr"

def _context_intents(text: str) -> List[str]:
    t = text.lower()
    intents = []
    emotional_words = (
        "feel", "feeling", "shit", "sad", "angry", "anxious", "overwhelmed", "spiral",
        "catastrophe", "catastrophizing", "ruined", "tired", "exhausted", "ashamed",
        "heartbreak", "miss him", "miss her", "cry", "crying",
    )
    planning_words = ("plan", "planning", "tomorrow", "week", "weekly", "today", "next", "sort", "organize")
    work_words = ("work", "shift", "shifts", "late shift", "late shifts", "job", "coworker", "client", "patient", "meeting")

    if _word_match(t, BUDGET_KEYWORDS):
        intents.append("budget")
    if _word_match(t, MEAL_KEYWORDS):
        intents.append("food")
    if _word_match(t, TRAINING_KEYWORDS):
        intents.append("training")
    if _word_match(t, emotional_words):
        intents.append("emotional support")
    if _word_match(t, work_words):
        intents.append("work stress")
    if _word_match(t, planning_words):
        intents.append("planning")
    if _word_match(t, CALENDAR_KEYWORDS):
        intents.append("calendar")
    if _word_match(t, LETTER_KEYWORDS):
        intents.append("letters")
    if _word_match(t, PATTERN_KEYWORDS):
        intents.append("patterns")
    if _word_match(t, DUMP_KEYWORDS):
        intents.append("brain dump")
    if not intents:
        intents.append("general conversation")
    return intents

def _spending_category_hint(text: str) -> Optional[str]:
    t = text.lower()
    hints = {
        "Monster/energy drinks": ("monster", "energy drink", "energy drinks"),
        "snus": ("snus",),
        "coffee": ("coffee",),
        "groceries": ("groceries", "grocery"),
        "candy/snacks": ("candy", "snack", "snacks"),
        "takeaway": ("takeaway", "takeout"),
        "transport": ("transport", "bus", "train", "taxi"),
        "random chaos purchases": ("random chaos", "random chaos purchases", "random nonsense", "nonsense"),
    }
    for category, words in hints.items():
        if any(word in t for word in words):
            return category
    return None

def _context_date_for_text(text: str):
    t = text.lower()
    today = _now_oslo().date()
    if "today" in t:
        return today.isoformat(), "today"
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat(), "yesterday"
    return None, None

def _budget_router_context(text: str) -> str:
    store = _read_life_store()
    month = _now_oslo().strftime("%Y-%m")
    setup = store.get("budget_setups", {}).get(month) or {"income": DEFAULT_INCOME, "fixed_expenses": DEFAULT_FIXED_EXPENSES}
    summary = _budget_summary(month, setup, store.get("spending", []))
    target_date, date_label = _context_date_for_text(text)
    category_hint = _spending_category_hint(text)
    spending = [s for s in store.get("spending", []) if (s.get("date") or "").startswith(month)]
    if target_date:
        spending = [s for s in spending if s.get("date") == target_date]
    if category_hint:
        spending = [s for s in spending if _normalize_spending_category(s.get("category") or "other") == category_hint]

    lines = [
        "budget:",
        f"- current month: income {_kr(summary['income_total'])}, fixed {_kr(summary['fixed_total'])}, flexible logged {_kr(summary['flexible_total'])}",
        f"- days checked in this month: {summary['checked_days']}/{summary['days_in_month']}",
    ]
    if category_hint or target_date:
        label = f"{category_hint or 'spending'} {date_label or 'this month'}"
        total = sum(float(s.get("amount") or 0) for s in spending)
        lines.append(f"- requested slice: {label} = {_kr(total)}")
    if summary.get("by_category"):
        top = sorted(summary["by_category"].items(), key=lambda item: item[1], reverse=True)[:5]
        lines.append("- category signals: " + ", ".join(f"{name} {_kr(value)}" for name, value in top))
    recent = sorted(spending, key=lambda x: x.get("timestamp") or x.get("date") or "", reverse=True)[:5]
    if recent:
        lines.append("- recent relevant logs: " + "; ".join(
            f"{s.get('date')}: {_kr(s.get('amount'))} {_normalize_spending_category(s.get('category') or 'other')}" for s in recent
        ))
    return "\n".join(lines)

def _food_router_context(text: str) -> str:
    store = _read_life_store()
    plans = store.get("food_plans", {})
    lines = ["food:"]
    if plans:
        latest_key = sorted(plans.keys())[-1]
        plan = plans[latest_key]
        inputs = plan.get("inputs", {})
        lines.extend([
            f"- active week starts {latest_key}",
            f"- breakfast default: {inputs.get('breakfast_default') or 'not set'}",
            f"- lunch system: {inputs.get('lunch_week') or 'not set'}",
            f"- protein rotation: {', '.join(inputs.get('protein_weeks') or [inputs.get('protein_week') or 'not set'])}",
            f"- budget feeling: {inputs.get('budget_feeling') or 'not set'}",
        ])
        if inputs.get("leftovers"):
            lines.append(f"- leftovers at home: {inputs.get('leftovers')}")
        if plan.get("grocery_estimate"):
            lines.append(f"- grocery estimate: {_kr(plan.get('grocery_estimate'))}")
        dinners = [d.get("dinner") for d in (plan.get("days") or [])[:7] if d.get("dinner")]
        if dinners:
            lines.append("- dinner rotation: " + ", ".join(dinners[:5]))
    else:
        lines.extend([
            "- no saved weekly food plan yet",
            "- default flow is Saturday-to-Saturday, one lunch system, one protein week, shopping list estimate in kr",
        ])
    return "\n".join(lines)

async def _recent_mongo_docs(collection_name: str, limit: int = 8, days: int = 30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        collection = getattr(db, collection_name)
        return await collection.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    except Exception:
        logging.warning("mongo unavailable for %s context", collection_name)
        return []

def _training_router_context(local_training: List[Dict[str, Any]], mongo_training: List[Dict[str, Any]], text: str) -> str:
    today_name = _now_oslo().strftime("%A").lower()
    today_date = _now_oslo().date().isoformat()
    expected = WEEKLY_TEMPLATE.get(today_name, {})
    entries = sorted([*local_training, *mongo_training], key=lambda x: x.get("timestamp") or x.get("date") or "", reverse=True)
    today_entries = [e for e in entries if e.get("date") == today_date]
    lines = [
        "training:",
        f"- today ({today_name}): {expected.get('focus', 'no template set')}",
    ]
    if any(word in text.lower() for word in ("skip", "skipped", "missed")):
        lines.append(f"- logged today: {'yes' if today_entries else 'no'}")
    if entries:
        recent = []
        for e in entries[:5]:
            bits = [e.get("date") or "", e.get("kind") or ""]
            if e.get("session_name"):
                bits.append(e["session_name"])
            if e.get("distance_km"):
                bits.append(f'{e["distance_km"]} km')
            if e.get("duration_min"):
                bits.append(f'{e["duration_min"]} min')
            recent.append(" ".join([b for b in bits if b]).strip())
        lines.append("- recent logs: " + "; ".join(recent))
    else:
        lines.append("- no recent workouts logged")
    lines.append("- Saturday or Sunday can be long run; Sunday still gets recovery-food attention in food planning.")
    return "\n".join(lines)

def _emotional_router_context(local_dumps: List[Dict[str, Any]], mongo_dumps: List[Dict[str, Any]]) -> str:
    dumps = sorted([*local_dumps, *mongo_dumps], key=lambda x: x.get("timestamp") or "", reverse=True)[:10]
    lines = ["emotional/energy:"]
    if not dumps:
        lines.append("- no recent brain dump signals logged")
        return "\n".join(lines)
    moods: Dict[str, int] = {}
    energies = []
    work_hits = 0
    for d in dumps:
        mood = d.get("mood")
        if mood:
            moods[mood] = moods.get(mood, 0) + 1
        if d.get("energy") is not None:
            try:
                energies.append(float(d.get("energy")))
            except (TypeError, ValueError):
                pass
        body = f"{d.get('text') or ''} {' '.join(d.get('tags') or [])}".lower()
        if any(word in body for word in ("work", "shift", "late", "job")):
            work_hits += 1
    if moods:
        lines.append("- recent mood tags: " + ", ".join(f"{k} x{v}" for k, v in sorted(moods.items())))
    if energies:
        lines.append(f"- average recent energy: {sum(energies) / len(energies):.1f}/5")
    if work_hits:
        lines.append(f"- work/shift appears in {work_hits} recent brain dump signal(s)")
    lines.append("- keep this light; do not inject emotional history unless the user explicitly asks.")
    return "\n".join(lines)

async def _calendar_router_context(limit: int = 5) -> str:
    try:
        cal = await calendar_today()
    except Exception:
        logging.warning("calendar unavailable for routed chat context")
        return ""
    if not cal.get("linked"):
        return "calendar:\n- calendar is not linked"
    events = cal.get("events") or []
    if not events:
        return "calendar:\n- linked; no events returned for today"
    lines = ["calendar today:"]
    for ev in events[:limit]:
        location = f" ({ev.get('location')})" if ev.get("location") else ""
        lines.append(f"- {ev.get('start', '')}: {ev.get('summary', '')}{location}")
    return "\n".join(lines)

async def _patterns_router_context() -> str:
    try:
        pattern_data = await patterns()
    except Exception:
        logging.warning("patterns unavailable for routed chat context")
        return ""
    observations = pattern_data.get("observations") or []
    if not observations:
        return ""
    lines = ["patterns:"]
    for obs in observations[:4]:
        lines.append(f"- {obs.get('title', '')}: {obs.get('body', '')}")
    return "\n".join(lines)

async def _letters_router_context() -> str:
    try:
        letters = await db.letters.find({}, {"_id": 0}).sort("generated_at", -1).to_list(3)
    except Exception:
        logging.warning("letters unavailable for routed chat context")
        return ""
    if not letters:
        return ""
    lines = ["recent letters:"]
    for letter in letters:
        body = (letter.get("body") or "").replace("\n", " ")[:260]
        lines.append(f"- {letter.get('week_key', '')}: {body}")
    return "\n".join(lines)

async def _gather_context_v2(text: str) -> str:
    intents = _context_intents(text)
    intent_set = set(intents)
    mixed = len(intent_set - {"planning"}) > 1
    store = _read_life_store()
    context_parts = []
    lower = text.lower()

    if "budget" in intent_set:
        context_parts.append(_budget_router_context(text))
    if "food" in intent_set or ("planning" in intent_set and any(w in lower for w in ("eat", "food", "meal", "shopping", "grocery"))):
        context_parts.append(_food_router_context(text))
    if "training" in intent_set or ("food" in intent_set and "week" in lower):
        mongo_training = await _recent_mongo_docs("training", limit=5)
        context_parts.append(_training_router_context(store.get("training", [])[-10:], mongo_training, text))
    if "emotional support" in intent_set or "work stress" in intent_set:
        mongo_dumps = await _recent_mongo_docs("braindumps", limit=8)
        context_parts.append(_emotional_router_context(store.get("braindumps", [])[-10:], mongo_dumps))
    if "work stress" in intent_set or "calendar" in intent_set:
        calendar_context = await _calendar_router_context()
        if calendar_context:
            context_parts.append(calendar_context)
    if "planning" in intent_set and not any(i in intent_set for i in ("food", "training", "budget", "calendar")):
        context_parts.append(_food_router_context(text))
        mongo_training = await _recent_mongo_docs("training", limit=4)
        context_parts.append(_training_router_context(store.get("training", [])[-8:], mongo_training, text))
    if "patterns" in intent_set:
        patterns_context = await _patterns_router_context()
        if patterns_context:
            context_parts.append(patterns_context)
    if "letters" in intent_set:
        letters_context = await _letters_router_context()
        if letters_context:
            context_parts.append(letters_context)
    if "brain dump" in intent_set and "emotional support" not in intent_set:
        mongo_dumps = await _recent_mongo_docs("braindumps", limit=6)
        context_parts.append(_emotional_router_context(store.get("braindumps", [])[-8:], mongo_dumps))
    if not context_parts:
        return ""

    visible_intent = "mixed" if mixed else intents[0]
    return (
        "CONTEXT ROUTER SUMMARY FROM CALM & CHAOS.\n"
        f"intent: {visible_intent}\n"
        "Use only these selected signals. This is retrieval, not a full app dump. "
        "Do not announce the router or mention database mechanics. Be naturally observant, "
        "specific when useful, and honest if a needed detail is not logged.\n\n"
        + "\n\n".join(context_parts)
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

def _format_user_message_with_history(history, current_text: str) -> str:
    """
    Build a single user-message string that includes recent conversation as memory,
    so the LLM only needs one API call instead of replaying every turn.
    history is a list of {role, text} dicts in chronological (oldest first) order.
    """
    if not history:
        return current_text
    lines = ["[recent room — last few exchanges, for memory; do not respond to these, only the message after [now]]"]
    for h in history:
        role = "me" if h.get("role") == "user" else "you"
        text = (h.get("text") or "").strip()
        if not text:
            continue
        # Light truncation per turn to keep budget tight
        if len(text) > 800:
            text = text[:800] + "…"
        lines.append(f"{role}: {text}")
    lines.append("")
    lines.append("[now]")
    lines.append(current_text)
    return "\n".join(lines)

@api_router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="empty text")
    if not (OPENAI_API_KEY or EMERGENT_LLM_KEY):
        raise HTTPException(status_code=500, detail="OpenAI key not configured")

    # 1. Fetch recent history BEFORE inserting the new one
    history = await _recent_history(limit=10)

    # 2. Persist the user message
    user_msg = ChatMessage(role="user", text=req.text.strip(), mode=req.mode)
    user_doc = user_msg.model_dump()
    user_doc["timestamp"] = user_doc["timestamp"].isoformat()
    try:
        await db.chat_messages.insert_one(user_doc)
    except Exception:
        logging.warning("mongo unavailable for user chat save; using local fallback")
        _append_local_chat_message(user_doc)

    # 3. Gather data-aware context based on what the user is asking about
    data_context = await _gather_context_v2(req.text)

    # 4. Build ONE user message with history baked in, then make a SINGLE LLM call
    system = _compose_system(req.mode, data_context=data_context)
    composed = _format_user_message_with_history(history, req.text.strip())

    try:
        reply_text = await _send_llm_message(system, composed, mode=req.mode)
    except Exception as e:
        logging.exception("LLM error")
        raise HTTPException(status_code=502, detail=f"goblin is quiet right now: {e}")

    assistant_msg = ChatMessage(role="assistant", text=str(reply_text).strip(), mode=req.mode)
    a_doc = assistant_msg.model_dump()
    a_doc["timestamp"] = a_doc["timestamp"].isoformat()
    try:
        await db.chat_messages.insert_one(a_doc)
    except Exception:
        logging.warning("mongo unavailable for assistant chat save; using local fallback")
        _append_local_chat_message(a_doc)

    return ChatResponse(reply=assistant_msg.text, user_msg=user_msg, assistant_msg=assistant_msg)

@api_router.get("/chat/recent")
async def chat_recent():
    try:
        docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(2)
        docs.reverse()
    except Exception:
        logging.warning("mongo unavailable for recent chat; using local fallback")
        docs = _local_chat_history(limit=2)
    return {"messages": docs}

@api_router.get("/chat/history")
async def chat_history():
    try:
        docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    except Exception:
        logging.warning("mongo unavailable for chat history route; using local fallback")
        docs = _read_local_chat_messages()
    return {"messages": docs}

@api_router.delete("/chat/history")
async def chat_clear():
    try:
        await db.chat_messages.delete_many({})
    except Exception:
        logging.warning("mongo unavailable for chat clear; clearing local fallback")
    _write_local_chat_messages([])
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
    try:
        await db.braindumps.insert_one(doc)
    except Exception:
        logging.warning("mongo unavailable for braindump save; using local fallback")
        _append_local_collection("braindumps", doc)
    return item

@api_router.get("/braindump")
async def braindump_list():
    try:
        docs = await db.braindumps.find({}, {"_id": 0}).sort("timestamp", -1).to_list(500)
    except Exception:
        logging.warning("mongo unavailable for braindump list; using local fallback")
        docs = _local_collection("braindumps")
    return {"entries": docs}

@api_router.delete("/braindump/{entry_id}")
async def braindump_delete(entry_id: str):
    try:
        await db.braindumps.delete_one({"id": entry_id})
    except Exception:
        logging.warning("mongo unavailable for braindump delete; using local fallback")
    _delete_local_collection("braindumps", entry_id)
    return {"ok": True}

# Training
WEEKLY_TEMPLATE = {
    "monday": {
        "focus": "Easy Run + Leg / Glute Day",
        "tags": ["run", "strength"],
        "run": {"label": "Easy run", "distance": "3.4 km"},
        "exercises": [
            {"name": "Hip thrust", "sets": 3, "reps": 8},
            {"name": "Kickback", "sets": 3, "reps": 8},
            {"name": "Hip abduction", "sets": 3, "reps": 8},
            {"name": "Romanian Deadlift (RDL)", "sets": 3, "reps": 8},
            {"name": "Lateral raises", "sets": 3, "reps": 8},
        ],
    },
    "tuesday": {"focus": "Rest or mobility", "tags": [], "exercises": []},
    "wednesday": {
        "focus": "Intervals + Upper / Core",
        "tags": ["run", "strength"],
        "run": {"label": "4x4 intervals", "distance": None},
        "exercises": [
            {"name": "Shoulder press", "sets": 3, "reps": 8},
            {"name": "Triceps", "sets": 3, "reps": 8},
            {"name": "Bicep curls", "sets": 3, "reps": 8},
            {"name": "Hammer curls", "sets": 3, "reps": 8},
            {"name": "Russian twist", "sets": 3, "reps": 10},
            {"name": "Sit-ups", "sets": 3, "reps": 10},
        ],
    },
    "thursday": {"focus": "Walk or rest", "tags": [], "exercises": []},
    "friday": {
        "focus": "Easy Run + Lower / Upper Mix",
        "tags": ["run", "strength"],
        "run": {"label": "Easy run", "distance": "3-4 km"},
        "exercises": [
            {"name": "Hip thrust", "sets": 3, "reps": 8},
            {"name": "Leg press", "sets": 3, "reps": 8},
            {"name": "Step-ups", "sets": 3, "reps": 8},
            {"name": "Lateral raises", "sets": 3, "reps": 8},
            {"name": "Lat pulldown", "sets": 3, "reps": 8},
            {"name": "Hammer curls", "sets": 3, "reps": 8},
            {"name": "Russian twist", "sets": 3, "reps": 10},
        ],
    },
    "saturday": {"focus": "Long Run", "tags": ["run"], "run": {"label": "Long run", "distance": None}, "exercises": []},
    "sunday": {"focus": "Long Run", "tags": ["run"], "run": {"label": "Long run", "distance": None}, "exercises": []},
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
    try:
        await db.training.insert_one(doc)
    except Exception:
        logging.exception("mongo unavailable for training save; using local fallback")
        _append_local_collection("training", doc)
    return entry

@api_router.get("/training")
async def training_list(limit: int = 100):
    try:
        docs = await db.training.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    except Exception:
        logging.warning("mongo unavailable for training list; using local fallback")
        docs = _local_collection("training", limit=limit)
    local_docs = _local_collection("training", limit=limit)
    seen = {doc.get("id") for doc in docs if doc.get("id")}
    for doc in local_docs:
        if doc.get("id") not in seen:
            docs.append(doc)
    docs = sorted(docs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    return {"entries": docs}

@api_router.delete("/training/{entry_id}")
async def training_delete(entry_id: str):
    try:
        await db.training.delete_one({"id": entry_id})
    except Exception:
        logging.warning("mongo unavailable for training delete; using local fallback")
    _delete_local_collection("training", entry_id)
    return {"ok": True}

# Strava OAuth + activity import
@api_router.get("/strava/status")
async def strava_status():
    token = await _read_strava_token()
    return {
        "configured": _strava_configured(),
        "linked": bool(token),
        "athlete": (_strava_token_preview(token) or {}).get("athlete") if token else None,
        "redirect_uri": STRAVA_REDIRECT_URI,
    }

@api_router.get("/strava/debug")
async def strava_debug():
    token = await _read_strava_token()
    events = []
    try:
        events = await db.oauth_debug.find(
            {"provider": "strava"},
            {"_id": 0},
        ).sort("timestamp", -1).to_list(10)
    except Exception:
        logging.warning("mongo unavailable for Strava debug read")
    return {
        "configured": _strava_configured(),
        "client_id_present": bool(STRAVA_CLIENT_ID),
        "client_secret_present": bool(STRAVA_CLIENT_SECRET),
        "app_public_url": APP_PUBLIC_URL,
        "frontend_url": FRONTEND_URL,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "linked": bool(token),
        "athlete": (_strava_token_preview(token) or {}).get("athlete") if token else None,
        "recent_events": events,
    }

@api_router.get("/oauth/strava/login")
async def strava_login(redirect: bool = False):
    if not _strava_configured():
        await _record_strava_debug("login_not_configured", {
            "client_id_present": bool(STRAVA_CLIENT_ID),
            "client_secret_present": bool(STRAVA_CLIENT_SECRET),
            "redirect_uri": STRAVA_REDIRECT_URI,
        })
        if redirect:
            return RedirectResponse(f"{FRONTEND_URL}/training?strava=error&reason=not_configured")
        raise HTTPException(status_code=500, detail="Strava is not configured")
    await _record_strava_debug("login_started", {"redirect": redirect, "redirect_uri": STRAVA_REDIRECT_URI})
    if redirect:
        return RedirectResponse(_strava_authorize_url())
    return {"url": _strava_authorize_url()}

@api_router.get("/oauth/strava/callback")
async def strava_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        await _record_strava_debug("callback_error", {"error": error})
        return RedirectResponse(f"{FRONTEND_URL}/training?strava=error&reason={error}")
    if not code:
        await _record_strava_debug("callback_missing_code")
        raise HTTPException(status_code=400, detail="missing Strava code")
    if not _strava_configured():
        await _record_strava_debug("callback_not_configured")
        raise HTTPException(status_code=500, detail="Strava is not configured")
    try:
        await _record_strava_debug("callback_code_received")
        token = _strava_exchange_code(code)
        await _write_strava_token(token)
        saved = await _read_strava_token()
        await _record_strava_debug("token_saved", {
            "linked_after_save": bool(saved),
            "athlete_id": ((saved or {}).get("athlete") or {}).get("id"),
        })
    except Exception:
        logging.exception("Strava OAuth callback failed")
        await _record_strava_debug("token_exchange_failed")
        return RedirectResponse(f"{FRONTEND_URL}/training?strava=error&reason=token_exchange_failed")
    return RedirectResponse(f"{FRONTEND_URL}/training?strava=linked")

@api_router.post("/strava/unlink")
async def strava_unlink():
    await _delete_strava_token()
    return {"ok": True}

@api_router.get("/strava/activities")
async def strava_activities(limit: int = 10):
    if not _strava_configured():
        raise HTTPException(status_code=500, detail="Strava is not configured")
    try:
        activities = await _strava_fetch_activities(limit)
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Strava activities fetch failed")
        raise HTTPException(status_code=502, detail=f"Strava refused to cooperate: {exc}")
    return {"activities": activities}

async def _strava_import_recent(limit: int = 10, types: Optional[List[str]] = None):
    if not _strava_configured():
        raise HTTPException(status_code=500, detail="Strava is not configured")
    try:
        activities = await _strava_fetch_activities(limit)
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Strava import failed")
        raise HTTPException(status_code=502, detail=f"Strava refused to cooperate: {exc}")

    allowed_types = {t.lower() for t in (types or ["run", "trailrun", "virtualrun", "ride", "walk"])}
    try:
        existing_docs = await db.training.find({"strava_id": {"$exists": True}}, {"_id": 0, "strava_id": 1}).to_list(1000)
    except Exception:
        logging.warning("mongo unavailable for Strava duplicate check; using local fallback")
        existing_docs = []
    store = _read_life_store()
    store.setdefault("training", [])
    existing_ids = {str(t.get("strava_id")) for t in existing_docs if t.get("strava_id")}
    existing_ids.update({str(t.get("strava_id")) for t in store["training"] if t.get("strava_id")})
    imported = []
    skipped = 0
    for activity in activities:
        activity_type = (activity.get("type") or activity.get("sport_type") or "").lower()
        if activity_type and activity_type not in allowed_types:
            skipped += 1
            continue
        strava_id = str(activity.get("id"))
        if strava_id in existing_ids:
            skipped += 1
            continue
        entry = _strava_activity_to_training(activity)
        if not entry:
            skipped += 1
            continue
        try:
            await db.training.insert_one(entry)
        except Exception:
            logging.warning("mongo unavailable for Strava import save; using local fallback")
            store["training"].append(entry)
        existing_ids.add(strava_id)
        imported.append(entry)
    store["training"] = store["training"][-500:]
    _write_life_store(store)
    return {"imported": imported, "imported_count": len(imported), "skipped_count": skipped}

@api_router.get("/strava/import/recent")
async def strava_import_recent(limit: int = 10, redirect: bool = False):
    try:
        result = await _strava_import_recent(limit=limit)
    except Exception as exc:
        if redirect:
            return RedirectResponse(f"{FRONTEND_URL}/training?strava_import=error&reason={type(exc).__name__}")
        raise
    if redirect:
        return RedirectResponse(
            f"{FRONTEND_URL}/training?strava_import=done"
            f"&imported={result.get('imported_count', 0)}"
            f"&skipped={result.get('skipped_count', 0)}"
        )
    return result

@api_router.post("/strava/import")
async def strava_import(req: StravaImportRequest):
    return await _strava_import_recent(limit=req.limit, types=req.types)

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

@api_router.get("/budget/v1")
async def budget_v1(month: Optional[str] = None):
    month = _month_key(month)
    store = _read_life_store()
    setup = store["budget_setups"].get(month) or {
        "month": month,
        "income": DEFAULT_INCOME,
        "income_notes": {},
        "fixed_expenses": DEFAULT_FIXED_EXPENSES,
        "fixed_notes": {},
        "fixed_active": {key: True for key in DEFAULT_FIXED_EXPENSES},
    }
    setup = {
        **setup,
        "income": {**DEFAULT_INCOME, **setup.get("income", {})},
        "income_notes": setup.get("income_notes", {}),
        "fixed_expenses": {**DEFAULT_FIXED_EXPENSES, **setup.get("fixed_expenses", {})},
        "fixed_notes": setup.get("fixed_notes", {}),
        "fixed_active": {key: setup.get("fixed_active", {}).get(key, True) for key in {**DEFAULT_FIXED_EXPENSES, **setup.get("fixed_expenses", {})}},
    }
    spending = [s for s in store["spending"] if (s.get("date") or "").startswith(month)]
    summary = _budget_summary(month, setup, store["spending"])
    return {
        "month": month,
        "setup": setup,
        "spending": sorted(spending, key=lambda x: x.get("date", ""), reverse=True),
        "summary": summary,
        "categories": SPENDING_CATEGORIES,
    }

@api_router.put("/budget/v1/setup")
async def budget_v1_setup(req: BudgetSetup):
    month = _month_key(req.month)
    store = _read_life_store()
    setup = {
        "month": month,
        "income": _money_dict({**DEFAULT_INCOME, **req.income}),
        "income_notes": {key: str(value or "") for key, value in req.income_notes.items()},
        "fixed_expenses": _money_dict({**DEFAULT_FIXED_EXPENSES, **req.fixed_expenses}),
        "fixed_notes": {key: str(value or "") for key, value in req.fixed_notes.items()},
        "fixed_active": {
            key: bool(req.fixed_active.get(key, True))
            for key in {**DEFAULT_FIXED_EXPENSES, **req.fixed_expenses}
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    store["budget_setups"][month] = setup
    _write_life_store(store)
    return {"setup": setup, "summary": _budget_summary(month, setup, store["spending"])}

@api_router.post("/budget/v1/spending", response_model=SpendingEntry)
async def budget_v1_spending(req: SpendingCreate):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    entry = SpendingEntry(**req.model_dump())
    if not entry.date:
        entry.date = datetime.now(timezone.utc).date().isoformat()
    entry.category = _normalize_spending_category(entry.category)
    doc = entry.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    store = _read_life_store()
    store["spending"].append(doc)
    store.setdefault("spending_checkins", [])
    if entry.date not in {c.get("date") for c in store["spending_checkins"]}:
        store["spending_checkins"].append({"date": entry.date, "timestamp": doc["timestamp"]})
    _write_life_store(store)
    return entry

@api_router.post("/budget/v1/checkin")
async def budget_v1_checkin(req: SpendingCheckinCreate):
    entry_date = req.date or datetime.now(timezone.utc).date().isoformat()
    store = _read_life_store()
    store.setdefault("spending_checkins", [])
    if entry_date not in {c.get("date") for c in store["spending_checkins"]}:
        store["spending_checkins"].append({
            "date": entry_date,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _write_life_store(store)
    month = _month_key(entry_date[:7])
    setup = store["budget_setups"].get(month) or {
        "month": month,
        "income": DEFAULT_INCOME,
        "income_notes": {},
        "fixed_expenses": DEFAULT_FIXED_EXPENSES,
        "fixed_notes": {},
        "fixed_active": {key: True for key in DEFAULT_FIXED_EXPENSES},
    }
    return {"ok": True, "summary": _budget_summary(month, setup, store["spending"])}

@api_router.delete("/budget/v1/spending/{entry_id}")
async def budget_v1_spending_delete(entry_id: str):
    store = _read_life_store()
    store["spending"] = [s for s in store["spending"] if s.get("id") != entry_id]
    _write_life_store(store)
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

@api_router.get("/food/v1")
async def food_v1(week_start: Optional[str] = None):
    week_start = _week_start(week_start)
    store = _read_life_store()
    plan = store["food_plans"].get(week_start)
    if not plan:
        plan = _food_plan(FoodPlanCreate(week_start=week_start))
    return {
        "week_start": week_start,
        "plan": plan,
        "lunch_options": ["chicken pasta salad", "rice bowls", "wraps", "soup + sandwich", "pasta bake"],
        "protein_options": list(DINNER_TEMPLATES.keys()),
        "budget_feelings": ["normal", "tighter", "treat week"],
    }

@api_router.put("/food/v1")
async def food_v1_save(req: FoodPlanCreate):
    plan = _food_plan(req)
    store = _read_life_store()
    store["food_plans"][plan["week_start"]] = plan
    _write_life_store(store)
    return {"plan": plan}

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
    ASSISTANT_SYSTEM +
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

    if not (OPENAI_API_KEY or EMERGENT_LLM_KEY):
        raise HTTPException(status_code=500, detail="OpenAI key not configured")

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

    try:
        text = await _send_llm_message(LETTER_SYSTEM, summary_blob, mode=f"letter-{week_key}")
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

def _read_local_calendar_token():
    if not LOCAL_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(LOCAL_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("failed reading local calendar token")
        return None

def _write_local_calendar_token(doc):
    LOCAL_TOKEN_FILE.write_text(json.dumps(doc, indent=2), encoding="utf-8")

async def _calendar_token_get():
    try:
        return await db.google_tokens.find_one({"user_id": SINGLE_USER_ID}, {"_id": 0})
    except Exception:
        logging.exception("mongo unavailable for calendar token read; using local fallback")
        return _read_local_calendar_token()

async def _calendar_token_save(doc):
    try:
        await db.google_tokens.update_one(
            {"user_id": SINGLE_USER_ID},
            {"$set": doc},
            upsert=True,
        )
    except Exception:
        logging.exception("mongo unavailable for calendar token save; using local fallback")
        _write_local_calendar_token(doc)

async def _calendar_token_update(update):
    doc = await _calendar_token_get() or {"user_id": SINGLE_USER_ID}
    doc.update(update)
    await _calendar_token_save(doc)

async def _calendar_token_delete():
    try:
        await db.google_tokens.delete_many({"user_id": SINGLE_USER_ID})
    except Exception:
        logging.exception("mongo unavailable for calendar token delete; clearing local fallback")
    if LOCAL_TOKEN_FILE.exists():
        LOCAL_TOKEN_FILE.unlink()

async def _record_calendar_debug(event: str, detail: Optional[Dict[str, Any]] = None):
    doc = {
        "provider": "google_calendar",
        "event": event,
        "detail": detail or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.oauth_debug.insert_one(doc)
    except Exception:
        logging.warning("mongo unavailable for calendar debug write")

@api_router.get("/calendar/status")
async def calendar_status():
    doc = await _calendar_token_get()
    return {"linked": bool(doc and (doc.get("refresh_token") or doc.get("access_token"))), "email": (doc or {}).get("email")}

@api_router.get("/calendar/debug")
async def calendar_debug():
    doc = await _calendar_token_get()
    events = []
    try:
        events = await db.oauth_debug.find(
            {"provider": "google_calendar"},
            {"_id": 0},
        ).sort("timestamp", -1).to_list(10)
    except Exception:
        logging.warning("mongo unavailable for calendar debug read")
    return {
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "client_id_present": bool(GOOGLE_CLIENT_ID),
        "client_secret_present": bool(GOOGLE_CLIENT_SECRET),
        "app_public_url": APP_PUBLIC_URL,
        "frontend_url": FRONTEND_URL,
        "redirect_uri": REDIRECT_URI,
        "linked": bool(doc and (doc.get("refresh_token") or doc.get("access_token"))),
        "email": (doc or {}).get("email"),
        "has_access_token": bool((doc or {}).get("access_token")),
        "has_refresh_token": bool((doc or {}).get("refresh_token")),
        "recent_events": events,
    }

@api_router.get("/oauth/calendar/login")
async def oauth_login(redirect: bool = False):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        await _record_calendar_debug("login_not_configured")
        if redirect:
            return RedirectResponse(f"{FRONTEND_URL}/?calendar=error&reason=google_credentials_missing")
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
    await _record_calendar_debug("login_started", {"redirect": redirect, "redirect_uri": REDIRECT_URI})
    if redirect:
        return RedirectResponse(url)
    return {"authorization_url": url}

@api_router.get("/oauth/calendar/callback")
async def oauth_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        await _record_calendar_debug("callback_error", {"error": error})
        return RedirectResponse(f"{FRONTEND_URL}/?calendar=error&reason={error}")
    if not code:
        await _record_calendar_debug("callback_missing_code")
        return RedirectResponse(f"{FRONTEND_URL}/?calendar=error&reason=missing_code")
    await _record_calendar_debug("callback_code_received")
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
        logging.warning("calendar oauth failed: %s", token_resp)
        await _record_calendar_debug("token_exchange_failed", {
            "error": token_resp.get("error"),
            "error_description": token_resp.get("error_description"),
        })
        return RedirectResponse(f"{FRONTEND_URL}/?calendar=error&reason=token_exchange_failed")

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
    await _calendar_token_save(save)
    saved = await _calendar_token_get()
    await _record_calendar_debug("token_saved", {
        "email": email,
        "has_access_token": bool((saved or {}).get("access_token")),
        "has_refresh_token": bool((saved or {}).get("refresh_token")),
    })
    return RedirectResponse(f"{FRONTEND_URL}/?calendar=linked")

@api_router.post("/calendar/unlink")
async def calendar_unlink():
    await _calendar_token_delete()
    return {"ok": True}

async def _get_creds():
    doc = await _calendar_token_get()
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
            await _calendar_token_update({"access_token": creds.token})
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
        tz = ZoneInfo(CALENDAR_TIMEZONE)
        today = datetime.now(tz).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=1)

        calendars = service.calendarList().list(
            minAccessRole="reader",
            showHidden=False,
        ).execute().get("items", [])
        if not calendars:
            calendars = [{"id": "primary", "summary": "Primary"}]

        events = []
        for cal in calendars:
            cal_id = cal.get("id")
            if not cal_id:
                continue
            resp = service.events().list(
                calendarId=cal_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            for ev in resp.get("items", []):
                start_t = ev.get("start", {})
                end_t = ev.get("end", {})
                events.append({
                    "id": f"{cal_id}:{ev.get('id')}",
                    "summary": ev.get("summary", "(untitled)"),
                    "start": start_t.get("dateTime") or start_t.get("date"),
                    "end": end_t.get("dateTime") or end_t.get("date"),
                    "all_day": "date" in start_t,
                    "location": ev.get("location"),
                    "calendar": cal.get("summary"),
                })

        def event_sort_key(ev):
            value = ev.get("start") or ""
            if len(value) == 10:
                return value + "T00:00:00"
            return value

        events.sort(key=event_sort_key)
        return {"linked": True, "events": events[:20]}
    except Exception as e:
        logging.exception("calendar fetch failed")
        return {"linked": False, "events": [], "error": str(e)}

app.include_router(api_router)

cors_origins = {
    "https://calm-and-chaos.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}
cors_origins.update(origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip())

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=sorted(cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
