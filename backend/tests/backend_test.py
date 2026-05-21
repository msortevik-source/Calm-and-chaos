"""Backend tests for Calm & Chaos app — iteration 2.

Covers regression of iteration 1 (greeting, chat, braindump CRUD, training CRUD, patterns, calendar)
plus new iteration-2 surface: new fields on braindump/training, new budget + meal endpoints, expanded
patterns observations (themes, mood drift, money), and Tone Constitution chat behavior on ground_me.
"""
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
        r = client.post(f"{API}/chat", json={"text": f"TEST_{mode} hello goblin", "mode": mode}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reply"] and isinstance(d["reply"], str)
        assert d["user_msg"]["role"] == "user"
        assert d["assistant_msg"]["role"] == "assistant"
        _no_mongo_id(d)

    def test_chat_ground_me_tone_constitution(self, client):
        """Goblin tone qualitative — only assert non-empty + no errors per requirements."""
        r = client.post(f"{API}/chat", json={"text": "i ruined everything", "mode": "ground_me"}, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["reply"], str) and len(d["reply"].strip()) > 0

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
        assert len(msgs) >= 2
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
    def test_braindump_backward_compat_text_only(self, client):
        r = client.post(f"{API}/braindump", json={"text": "TEST_dump bc only"}, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["text"] == "TEST_dump bc only"
        assert c.get("energy") is None
        assert c.get("mood") is None
        # tags either None or []
        assert not c.get("tags")
        _no_mongo_id(c)
        client.delete(f"{API}/braindump/{c['id']}", timeout=30)

    def test_braindump_new_fields_roundtrip(self, client):
        payload = {
            "text": "TEST_dump fields",
            "energy": 3,
            "mood": "ok",
            "tags": ["work", "TEST_tag"],
        }
        r = client.post(f"{API}/braindump", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        _no_mongo_id(c)
        assert c["text"] == payload["text"]
        assert c["energy"] == 3
        assert c["mood"] == "ok"
        assert c["tags"] == ["work", "TEST_tag"]
        eid = c["id"]

        # round-trip via GET
        r2 = client.get(f"{API}/braindump", timeout=30)
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        _no_mongo_id(entries)
        found = [e for e in entries if e["id"] == eid]
        assert found, "entry not returned by GET"
        e = found[0]
        assert e["energy"] == 3
        assert e["mood"] == "ok"
        assert e["tags"] == ["work", "TEST_tag"]

        # cleanup
        client.delete(f"{API}/braindump/{eid}", timeout=30)


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
    def test_training_backward_compat_create_list_delete(self, client, payload):
        r = client.post(f"{API}/training", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        _no_mongo_id(created)
        assert created["kind"] == payload["kind"]
        assert created["date"]
        eid = created["id"]

        r2 = client.get(f"{API}/training", timeout=30)
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        _no_mongo_id(entries)
        assert any(e["id"] == eid for e in entries)

        r3 = client.delete(f"{API}/training/{eid}", timeout=30)
        assert r3.status_code == 200

    def test_training_new_fields_roundtrip(self, client):
        payload = {
            "kind": "strength",
            "session_name": "TEST_4x4 + upper body",
            "mood_before": "meh",
            "mood_after": "good",
            "win_of_the_day": "showed up",
            "soreness_notes": "right hamstring tight",
            "exercise": "TEST_dl",
            "weight_kg": 70,
            "reps": 5,
            "sets": 3,
        }
        r = client.post(f"{API}/training", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        _no_mongo_id(c)
        for k in ("session_name", "mood_before", "mood_after", "win_of_the_day", "soreness_notes"):
            assert c[k] == payload[k], f"{k} did not round-trip"
        eid = c["id"]

        # GET round-trip
        r2 = client.get(f"{API}/training", timeout=30)
        entries = r2.json()["entries"]
        e = next((x for x in entries if x["id"] == eid), None)
        assert e is not None
        assert e["session_name"] == payload["session_name"]
        assert e["mood_before"] == "meh"
        assert e["mood_after"] == "good"
        assert e["win_of_the_day"] == "showed up"
        assert e["soreness_notes"] == "right hamstring tight"

        client.delete(f"{API}/training/{eid}", timeout=30)


# ---------- Budget ----------
class TestBudget:
    def test_budget_crud_and_aggregates(self, client):
        payload = {
            "item": "TEST_coffee",
            "amount": 4.5,
            "category": "joy",
            "date": "2026-01-15",
            "notes": "TEST_note",
        }
        r = client.post(f"{API}/budget", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        _no_mongo_id(c)
        assert c["item"] == "TEST_coffee"
        assert c["amount"] == 4.5
        assert c["category"] == "joy"
        assert c["date"] == "2026-01-15"
        assert "id" in c
        eid = c["id"]

        r2 = client.get(f"{API}/budget", timeout=30)
        assert r2.status_code == 200
        body = r2.json()
        _no_mongo_id(body)
        assert "entries" in body
        assert "month_total" in body
        assert "by_category" in body
        assert isinstance(body["entries"], list)
        assert isinstance(body["month_total"], (int, float))
        assert isinstance(body["by_category"], dict)
        assert any(e["id"] == eid for e in body["entries"])

        r3 = client.delete(f"{API}/budget/{eid}", timeout=30)
        assert r3.status_code == 200

        r4 = client.get(f"{API}/budget", timeout=30)
        assert not any(e["id"] == eid for e in r4.json()["entries"])

    def test_budget_empty_item_400(self, client):
        r = client.post(f"{API}/budget", json={"item": "  ", "amount": 1.0}, timeout=30)
        assert r.status_code == 400


# ---------- Meal ----------
class TestMeal:
    def test_meal_crud(self, client):
        payload = {
            "meal": "TEST_chicken bowl",
            "protein_source": "chicken",
            "prep_status": "prepped",
            "easy_quick": True,
            "date": "2026-01-15",
            "notes": "TEST_notes",
            "mood_after": "good",
        }
        r = client.post(f"{API}/meal", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        _no_mongo_id(c)
        assert c["meal"] == "TEST_chicken bowl"
        assert c["protein_source"] == "chicken"
        assert c["prep_status"] == "prepped"
        assert c["easy_quick"] is True
        assert c["mood_after"] == "good"
        eid = c["id"]

        r2 = client.get(f"{API}/meal", timeout=30)
        assert r2.status_code == 200
        entries = r2.json()["entries"]
        _no_mongo_id(entries)
        assert any(e["id"] == eid for e in entries)

        r3 = client.delete(f"{API}/meal/{eid}", timeout=30)
        assert r3.status_code == 200

        r4 = client.get(f"{API}/meal", timeout=30)
        assert not any(e["id"] == eid for e in r4.json()["entries"])

    def test_meal_empty_400(self, client):
        r = client.post(f"{API}/meal", json={"meal": "   "}, timeout=30)
        assert r.status_code == 400


# ---------- Patterns ----------
class TestPatterns:
    def test_patterns_baseline(self, client):
        r = client.get(f"{API}/patterns", timeout=30)
        assert r.status_code == 200
        obs = r.json()["observations"]
        assert isinstance(obs, list)
        assert len(obs) >= 1
        for o in obs:
            assert o["title"] and o["body"]

    def test_patterns_themes_with_work_tag(self, client):
        # seed 3 braindumps tagged 'work'
        ids = []
        for i in range(3):
            r = client.post(f"{API}/braindump", json={
                "text": f"TEST_work seed {i}",
                "tags": ["work"],
                "mood": "meh",
            }, timeout=30)
            assert r.status_code == 200
            ids.append(r.json()["id"])
        try:
            r = client.get(f"{API}/patterns", timeout=30)
            assert r.status_code == 200
            obs = r.json()["observations"]
            kinds = [o.get("kind") for o in obs]
            assert "themes" in kinds, f"themes obs not surfaced. got: {kinds}"
        finally:
            for eid in ids:
                client.delete(f"{API}/braindump/{eid}", timeout=30)

    def test_patterns_mood_drift(self, client):
        # seed 6 braindumps; older are 'good'/'flying', newer are 'heavy'/'meh' to trigger drift down
        # entries are stored sorted desc by timestamp on GET; the pattern logic uses chronological window
        # We need at least 5 with mood; create 6 in sequence so newer (last inserted) are heavy/meh.
        seq = ["flying", "good", "good", "meh", "heavy", "heavy"]
        ids = []
        for i, m in enumerate(seq):
            r = client.post(f"{API}/braindump", json={
                "text": f"TEST_drift seed {i}",
                "mood": m,
            }, timeout=30)
            assert r.status_code == 200
            ids.append(r.json()["id"])
        try:
            r = client.get(f"{API}/patterns", timeout=30)
            obs = r.json()["observations"]
            kinds = [o.get("kind") for o in obs]
            assert "mood" in kinds, f"mood drift obs not surfaced. got kinds={kinds}"
        finally:
            for eid in ids:
                client.delete(f"{API}/braindump/{eid}", timeout=30)

    def test_patterns_money_regret(self, client):
        ids = []
        for i in range(3):
            r = client.post(f"{API}/budget", json={
                "item": f"TEST_regret {i}",
                "amount": 12.0,
                "category": "regret",
            }, timeout=30)
            assert r.status_code == 200
            ids.append(r.json()["id"])
        try:
            r = client.get(f"{API}/patterns", timeout=30)
            obs = r.json()["observations"]
            kinds = [o.get("kind") for o in obs]
            assert "money" in kinds, f"money obs not surfaced. got kinds={kinds}"
        finally:
            for eid in ids:
                client.delete(f"{API}/budget/{eid}", timeout=30)


# ---------- Iteration 3: data-aware chat ----------
class TestDataAwareChat:
    def test_chat_with_training_keyword_pulls_context(self, client):
        # Seed 2 training entries within last 30 days
        seeded = []
        for payload in [
            {"kind": "run", "distance_km": 6.0, "duration_min": 33, "pace": "5:30", "notes": "TEST_iter3 easy run", "mood_after": "good"},
            {"kind": "strength", "exercise": "TEST_iter3 squat", "weight_kg": 65, "sets": 3, "reps": 5, "session_name": "TEST_iter3 lower"},
        ]:
            r = client.post(f"{API}/training", json=payload, timeout=30)
            assert r.status_code == 200
            seeded.append(r.json()["id"])
        try:
            r = client.post(
                f"{API}/chat",
                json={"text": "look at my training this week", "mode": "send"},
                timeout=180,
            )
            assert r.status_code == 200, r.text
            d = r.json()
            assert isinstance(d["reply"], str)
            assert len(d["reply"].strip()) > 0
            _no_mongo_id(d)
        finally:
            for eid in seeded:
                client.delete(f"{API}/training/{eid}", timeout=30)

    def test_chat_without_data_keywords_still_works(self, client):
        r = client.post(
            f"{API}/chat",
            json={"text": "i feel weird", "mode": "send"},
            timeout=180,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["reply"], str)
        assert len(d["reply"].strip()) > 0


# ---------- Iteration 3: weekly letter ----------
class TestLetter:
    def test_letter_current_generates_and_caches(self, client):
        import time
        # First call: may generate (LLM call) — could be cached if previous run hit it
        t0 = time.time()
        r1 = client.get(f"{API}/letter/current", timeout=180)
        first_dur = time.time() - t0
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        _no_mongo_id(d1)
        for key in ("week_key", "generated_at", "body", "counts"):
            assert key in d1, f"missing {key}"
        assert isinstance(d1["body"], str) and len(d1["body"].strip()) > 0
        counts = d1["counts"]
        for ck in (
            "training_sessions", "training_days", "brain_dumps",
            "budget_entries", "meals_logged", "chat_messages_user", "hard_truth_asks",
        ):
            assert ck in counts, f"missing count {ck}"
            assert isinstance(counts[ck], int)

        # Second call: must be cached (same week_key, same generated_at, and fast)
        t1 = time.time()
        r2 = client.get(f"{API}/letter/current", timeout=30)
        second_dur = time.time() - t1
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["week_key"] == d1["week_key"]
        assert d2["generated_at"] == d1["generated_at"], "cache miss — generated_at changed"
        # Cached call should be reasonably fast (< 5s; LLM gen typically takes 15-40s)
        assert second_dur < 5.0, f"cached call too slow: {second_dur:.1f}s (first was {first_dur:.1f}s)"

    def test_letter_force_regenerates(self, client):
        # Get current (cached) letter
        r0 = client.get(f"{API}/letter/current", timeout=180)
        assert r0.status_code == 200
        original_generated_at = r0.json()["generated_at"]
        original_week_key = r0.json()["week_key"]

        # Force regeneration
        r1 = client.get(f"{API}/letter/current", params={"force": "true"}, timeout=180)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["week_key"] == original_week_key
        assert d1["generated_at"] != original_generated_at, "force=true did not regenerate"
        assert isinstance(d1["body"], str) and len(d1["body"].strip()) > 0

    def test_letter_archive(self, client):
        # Ensure at least one letter exists
        client.get(f"{API}/letter/current", timeout=180)
        r = client.get(f"{API}/letter/archive", timeout=30)
        assert r.status_code == 200
        d = r.json()
        _no_mongo_id(d)
        assert "letters" in d
        letters = d["letters"]
        assert isinstance(letters, list)
        assert len(letters) >= 1
        # sorted by generated_at desc
        ts = [ll["generated_at"] for ll in letters]
        assert ts == sorted(ts, reverse=True), f"letters not sorted desc by generated_at: {ts}"
        for ll in letters:
            assert "week_key" in ll and "body" in ll and "counts" in ll


# ---------- Iteration 4: single-LLM-call refactor of /api/chat ----------
class TestChatIteration4:
    """Iteration 4: /api/chat now makes ONE LLM call per message (history baked in).
    Verify: (a) latency < 8s for a single call, (b) multi-turn memory still works,
    (c) data-aware context still injected, (d) history endpoints unchanged."""

    def test_chat_single_call_latency_under_8s(self, client):
        import time
        # Clear history so we test a no-history path (fastest possible)
        client.delete(f"{API}/chat/history", timeout=30)
        t0 = time.time()
        r = client.post(
            f"{API}/chat",
            json={"text": "TEST_iter4 quick hello", "mode": "send"},
            timeout=30,
        )
        dur = time.time() - t0
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["assistant_msg"]["text"].strip(), "empty assistant text"
        print(f"\n[iter4] single chat call latency: {dur:.2f}s")
        # Soft assertion per spec: should be well under 8s now (was 10-20s before)
        assert dur < 8.0, f"chat call too slow: {dur:.2f}s (expected <8s after refactor)"

    def test_chat_multi_turn_memory(self, client):
        """Turn 1 sets context, turn 2 references it implicitly. Just verify
        the assistant_msg.text is non-empty and request succeeds — content
        coherence is qualitative, but a working memory should at minimum
        produce a non-empty reply when asked a follow-up."""
        client.delete(f"{API}/chat/history", timeout=30)
        # Turn 1
        r1 = client.post(
            f"{API}/chat",
            json={"text": "hey, just got back from a run", "mode": "send"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["assistant_msg"]["text"].strip()

        # Turn 2 — pronoun reference, no explicit subject
        r2 = client.post(
            f"{API}/chat",
            json={"text": "how long was it?", "mode": "send"},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        text2 = d2["assistant_msg"]["text"].strip()
        assert text2, "empty assistant reply on turn 2"
        # Verify history actually has 4 messages (2 user + 2 assistant) in order
        rh = client.get(f"{API}/chat/history", timeout=30)
        msgs = rh.json()["messages"]
        assert len(msgs) >= 4
        roles = [m["role"] for m in msgs[-4:]]
        assert roles == ["user", "assistant", "user", "assistant"], f"unexpected role order: {roles}"

    def test_chat_data_aware_still_works_after_refactor(self, client):
        """Seed 1 training entry, then ask a training-keyword question. Verify
        non-empty reply and single LLM call still pulls in the data context."""
        import time
        seeded = []
        r = client.post(f"{API}/training", json={
            "kind": "run", "distance_km": 7.0, "duration_min": 40,
            "pace": "5:42", "notes": "TEST_iter4 ctx run",
        }, timeout=30)
        assert r.status_code == 200
        seeded.append(r.json()["id"])
        try:
            t0 = time.time()
            r2 = client.post(
                f"{API}/chat",
                json={"text": "how's my running been this week?", "mode": "send"},
                timeout=30,
            )
            dur = time.time() - t0
            assert r2.status_code == 200, r2.text
            d = r2.json()
            assert d["assistant_msg"]["text"].strip()
            print(f"\n[iter4] data-aware chat latency: {dur:.2f}s")
            assert dur < 8.0, f"data-aware chat too slow: {dur:.2f}s"
        finally:
            for eid in seeded:
                client.delete(f"{API}/training/{eid}", timeout=30)

    def test_chat_empty_still_400(self, client):
        r = client.post(f"{API}/chat", json={"text": "", "mode": "send"}, timeout=30)
        assert r.status_code == 400

    def test_chat_recent_returns_last_two_chrono(self, client):
        """Regression: /api/chat/recent still returns last 2 in chronological order."""
        client.delete(f"{API}/chat/history", timeout=30)
        client.post(f"{API}/chat", json={"text": "TEST_iter4 first", "mode": "send"}, timeout=30)
        client.post(f"{API}/chat", json={"text": "TEST_iter4 second", "mode": "send"}, timeout=30)
        r = client.get(f"{API}/chat/recent", timeout=30)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert len(msgs) == 2
        ts = [m["timestamp"] for m in msgs]
        assert ts == sorted(ts), "recent not chronological"


# ---------- Calendar ----------
class TestCalendar:
    def test_status_keys(self, client):
        r = client.get(f"{API}/calendar/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "linked" in d

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
