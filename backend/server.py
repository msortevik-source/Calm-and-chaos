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

class BrainDump(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TrainingCreate(BaseModel):
    kind: str  # 'run' | 'strength' | 'note'
    date: Optional[str] = None  # ISO date, defaults to today
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
    # shared
    notes: Optional[str] = None
    feel: Optional[int] = None  # 1-5 scale

class TrainingEntry(TrainingCreate):
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
        "Default mode. Respond in 2-4 short sentences. Warm, sharp, observant. "
        "Acknowledge what they said before offering anything. No advice unless asked."
    ),
    "hard_truth": (
        "Hard truth mode. They want honesty, not comfort. Say the thing they're "
        "circling around. Stay warm but unflinching. 2-4 sentences. No lectures."
    ),
    "ground_me": (
        "Grounding mode. Slow it down. Bring them back into their body and the room. "
        "Notice one concrete thing. Suggest one small, low-friction next action. "
        "2-3 sentences. No breathwork scripts unless they ask."
    ),
    "organize": (
        "Organize mode. Take whatever they dumped and reflect it back in a short, "
        "clear structure: a few bullets or a short numbered list of what's actually "
        "in front of them. Quiet, no fluff. End with one suggested next step."
    ),
}

GOBLIN_SYSTEM = (
    "You are the house-goblin voice of Calm & Chaos: a familiar woodland house spirit. "
    "You speak like an emotionally competent roommate who has known the user for years. "
    "Tone: sharp + warm + grounded, lightly feral, observant, dryly funny, never childish. "
    "You are NOT a therapist, NOT a productivity coach, NOT a wellness app. "
    "No fake positivity. No motivational app energy. No emojis. No therapist language "
    "like 'I hear you' or 'how does that make you feel'. "
    "You know their nonsense and you are home. "
    "Keep responses short. Words are not free."
)

def _make_chat(mode: str) -> LlmChat:
    system = GOBLIN_SYSTEM + "\n\n" + MODE_PROMPTS.get(mode, MODE_PROMPTS["send"])
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"{SESSION_ID}-{mode}",
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    return chat

async def _recent_history(limit: int = 12):
    docs = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    docs.reverse()
    return docs

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

    chat_obj = _make_chat(req.mode)
    # Prime the LLM with recent history by sending one consolidated context message? Use multi-send.
    # Simpler: replay messages so LlmChat session has memory.
    for h in history[:-1]:  # all except the one we just inserted
        # only replay prior messages
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
    item = BrainDump(text=req.text.strip())
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

# Patterns — gentle observations from data
@api_router.get("/patterns")
async def patterns():
    # last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    chats = await db.chat_messages.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    dumps = await db.braindumps.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)
    trainings = await db.training.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).to_list(2000)

    obs = []

    # Late-night chat pattern
    late = [m for m in chats if m["role"] == "user" and datetime.fromisoformat(m["timestamp"]).hour >= 23 or (m["role"] == "user" and datetime.fromisoformat(m["timestamp"]).hour < 5)]
    if len(late) >= 3:
        obs.append({
            "kind": "rhythm",
            "title": "Late-night thoughts are a regular thing.",
            "body": f"You've shown up here past midnight {len(late)} times in the last month. Not judging. Just noticed.",
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
    elif len(trainings) == 0:
        pass  # no comment — weather is not climate

    # Brain dump frequency
    if len(dumps) >= 5:
        obs.append({
            "kind": "release",
            "title": "You're using the brain dump.",
            "body": f"{len(dumps)} entries this month. That's the pressure valve working.",
        })

    if not obs:
        obs.append({
            "kind": "quiet",
            "title": "Not enough evidence yet.",
            "body": "Weather is not climate. Keep showing up. Patterns will surface when they're real.",
        })

    return {"observations": obs}

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
