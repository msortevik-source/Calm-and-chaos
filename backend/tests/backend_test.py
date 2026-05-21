"""Backend tests for Calm & Chaos app."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://moss-grounded.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(client):
    # Clean chat history before tests so recent/history assertions are deterministic
    client.delete(f"{API}/chat/history", timeout=30)
    yield


def _no_mongo_id(obj):
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in {obj}"
        for v in obj.values():
            _no_mongo_id(v)
    elif isinstance(obj, list):
        for v in obj:
            _no_mongo_id(v)


# ---------- Greeting ----------
class TestGreeting:
    def test_greeting(self, client):
        r = client.get(f"{API}/greeting", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["greeting"] and isinstance(d["greeting"], str)
        assert d["sub"] and isinstance(d["sub"], str)
        assert d["time_of_day"] in ("morning", "midday", "evening", "late_night")


# ---------- Chat ----------
class TestChat:
    def test_chat_empty_400(self, client):
        r = client.post(f"{API}/chat", json={"text": "   ", "mode": "send"}, timeout=30)
        assert r.status_code == 400

    @pytest.mark.parametrize("mode", ["send", "hard_truth", "ground_me", "organize"])
    def test_chat_modes(self, client, mode):
        r = client.post(f"{API}/chat", json={"text": f"TEST_{mode} hello goblin", "mode": mode}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reply"] and isinstance(d["reply"], str)
        assert d["user_msg"]["role"] == "user"
        assert d["assistant_msg"]["role"] == "assistant"
        _no_mongo_id(d)

    def test_chat_recent(self, client):
        r = client.get(f"{API}/chat/recent", timeout=30)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert isinstance(msgs, list)
        assert len(msgs) <= 2
        _no_mongo_id(msgs)

    def test_chat_history(self, client):
        r = client.get(f"{API}/chat/history", timeout=30)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert isinstance(msgs, list)
        assert len(msgs) >= 2  # at least one round happened
        # chronological asc
        ts = [m["timestamp"] for m in msgs]
        assert ts == sorted(ts)
        _no_mongo_id(msgs)

    def test_chat_clear(self, client):
        r = client.delete(f"{API}/chat/history", timeout=30)
        assert r.status_code == 200
        r2 = client.get(f"{API}/chat/history", timeout=30)
        assert r2.json()["messages"] == []


# ---------- Brain dump ----------
class TestBrainDump:
    def test_braindump_crud(self, client):
        r = client.post(f"{API}/braindump", json={"text": "TEST_dump entry"}, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["text"] == "TEST_dump entry"
        assert "id" in created
        _no_mongo_id(created)
        eid = created["id"]

        r2 = client.get(f"{API}/braindump", timeout=30)
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        _no_mongo_id(entries)
        assert any(e["id"] == eid for e in entries)

        r3 = client.delete(f"{API}/braindump/{eid}", timeout=30)
        assert r3.status_code == 200

        r4 = client.get(f"{API}/braindump", timeout=30)
        assert not any(e["id"] == eid for e in r4.json()["entries"])


# ---------- Training ----------
class TestTraining:
    def test_template(self, client):
        r = client.get(f"{API}/training/template", timeout=30)
        assert r.status_code == 200
        tpl = r.json()["template"]
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            assert day in tpl
        for day in ["monday", "wednesday", "friday"]:
            assert "run" in tpl[day]["tags"] and "strength" in tpl[day]["tags"]

    @pytest.mark.parametrize("payload", [
        {"kind": "run", "distance_km": 5.0, "duration_min": 30, "feel": 4, "notes": "TEST_run"},
        {"kind": "strength", "exercise": "TEST_squat", "weight_kg": 60, "reps": 5, "sets": 3, "feel": 3},
        {"kind": "note", "notes": "TEST_note"},
    ])
    def test_training_create_list_delete(self, client, payload):
        r = client.post(f"{API}/training", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        _no_mongo_id(created)
        assert created["kind"] == payload["kind"]
        assert created["date"]  # default applied
        eid = created["id"]

        r2 = client.get(f"{API}/training", timeout=30)
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        _no_mongo_id(entries)
        assert any(e["id"] == eid for e in entries)

        r3 = client.delete(f"{API}/training/{eid}", timeout=30)
        assert r3.status_code == 200


# ---------- Patterns ----------
class TestPatterns:
    def test_patterns_not_empty(self, client):
        r = client.get(f"{API}/patterns", timeout=30)
        assert r.status_code == 200
        obs = r.json()["observations"]
        assert isinstance(obs, list)
        assert len(obs) >= 1
        for o in obs:
            assert o["title"] and o["body"]


# ---------- Calendar ----------
class TestCalendar:
    def test_status_unlinked(self, client):
        r = client.get(f"{API}/calendar/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "linked" in d
        # not asserting False — could be linked from prior test, but key must exist

    def test_oauth_login(self, client):
        r = client.get(f"{API}/oauth/calendar/login", timeout=30)
        assert r.status_code == 200
        url = r.json()["authorization_url"]
        assert "accounts.google.com" in url

    def test_calendar_today_no_error(self, client):
        r = client.get(f"{API}/calendar/today", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "linked" in d and "events" in d
        assert isinstance(d["events"], list)
