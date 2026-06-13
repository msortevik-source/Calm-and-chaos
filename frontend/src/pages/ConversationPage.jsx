import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ChatInput from "../components/ChatInput";
import { getChatHistory, sendChat, clearChat } from "../lib/api";
import { renderInline } from "../lib/markdown";
import { CalendarDays, CalendarRange, Trash2 } from "lucide-react";
import { toast } from "sonner";

const LOADING_LINES = [
  "Reviewing the records.",
  "Checking the map against reality.",
  "Looking for the quiet pattern.",
  "Sorting signal from weather.",
];

export default function ConversationPage() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [seed, setSeed] = useState("");
  const [summaryPlaceholder, setSummaryPlaceholder] = useState(null);
  const endRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();

  const load = async () => {
    const d = await getChatHistory();
    setMessages(d.messages || []);
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (location.state && location.state.seed) {
      setSeed(location.state.seed);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!busy) {
      setLoadingIndex(0);
      return undefined;
    }
    const id = window.setInterval(() => {
      setLoadingIndex((prev) => (prev + 1) % LOADING_LINES.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [busy]);

  const submit = async (text, mode) => {
    setSummaryPlaceholder(null);
    setBusy(true);
    const tempId = "tmp-" + Date.now();
    setMessages((m) => [...m, { id: tempId, role: "user", text, mode, timestamp: new Date().toISOString() }]);
    try {
      const res = await sendChat(text, mode);
      setMessages((m) => m.filter((x) => x.id !== tempId).concat([res.user_msg, res.assistant_msg]));
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== tempId));
      toast("Analysis didn't return.", { description: e?.response?.data?.detail || "" });
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    if (!window.confirm("Clear the analysis history?")) return;
    await clearChat();
    setMessages([]);
  };

  const requestSummary = (type) => {
    const prompt = type === "weekly"
      ? `Give me a weekly summary from the app data.

Tone: calm, grounded, emotionally intelligent, observant, practical, and lightly funny if it fits.
Do not sound like a disappointed accountant, fitness coach, productivity app, or report card.

Important interpretation rules:
- Never assume missing logs mean failure. Say "not logged" or "tracking may be incomplete."
- Treat gaps as data quality or capacity signals, not moral problems.
- Pattern observations should be curious, not judgmental.
- Avoid shame, guilt loops, scolding, motivational-coach language, and dramatic conclusions.
- Consider recovery, stress, social load, late shifts, sleep disruption, grief/low-capacity periods, and life admin if reflected in the app data.

Include:
1. Training / movement: completed or not logged, manual gym/run logs, recovery context if visible.
2. Budget/spending: cycle-aware spending overview, category patterns, and gentle observations.
3. Calendar/planning/recovery notes if useful.
4. The Real Story This Week: a compassionate synthesis of what the week actually looked like.
5. One practical adjustment for next week.

Preferred phrasing:
- "No workouts logged this week (or tracking may be incomplete)."
- "Looks like convenience/dopamine spending may have crept in. Worth noticing, not panicking."
- "This may have been a recovery/capacity week rather than avoidance."

Goal: pattern awareness and momentum, not perfection.`
      : "Give me a monthly summary from the app data. Include training sessions, running volume, long-run/easy-run trend, strength progression, budget income/fixed/flexible/category breakdown, what quietly improved, main friction point, and one practical adjustment for next month.";
    submit(prompt, "send");
  };

  return (
    <div className="room-spirit px-5 md:px-12 py-7 md:py-16 max-w-4xl mx-auto" data-testid="conversation-page">
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">House spirit</div>
          <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Record Review</h1>
        </div>
        <button data-testid="clear-conversation" onClick={clear} className="pill-btn rounded-full px-3 py-1.5 text-xs inline-flex items-center gap-1.5">
          <Trash2 size={13} /> Clear
        </button>
      </div>

      <div className="warm-card rounded-3xl p-5 mb-8" data-testid="summary-actions">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-3">Stored observations</div>
        <div className="flex flex-wrap gap-3">
          <button data-testid="weekly-summary-button" disabled={busy} onClick={() => requestSummary("weekly")} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <CalendarDays size={14} /> Weekly record
          </button>
          <button data-testid="monthly-summary-button" disabled={busy} onClick={() => requestSummary("monthly")} className="pill-btn rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <CalendarRange size={14} /> Monthly record
          </button>
        </div>
        {summaryPlaceholder && (
          <div className="mt-4 rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4" data-testid={`${summaryPlaceholder}-summary-placeholder`}>
            <div className="text-[10px] uppercase tracking-[0.22em] text-amber/80 mb-2">
              {summaryPlaceholder === "weekly" ? "Weekly Summary" : "Monthly Summary"}
            </div>
            <p className="text-sm text-moss-100 leading-relaxed">
              Placeholder wired. Next pass builds the actual retrieval: training, Strava, budget, calendar context, and pattern notes. Receipts first, theatrical nonsense never.
            </p>
          </div>
        )}
      </div>

      <div className="space-y-6 mb-10" data-testid="messages">
        {messages.length === 0 && (
          <p className="text-moss-200 italic font-body">No observations yet. Ask what changed, what slipped, or where the money went.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`rounded-2xl p-5 ${m.role === "user" ? "warm-card" : "warm-card border-amber/30"}`} style={m.role === "assistant" ? { background: "linear-gradient(180deg, rgba(212,163,115,0.10) 0%, rgba(43,47,42,0.85) 100%)" } : undefined}>
            <div className={`text-[10px] uppercase tracking-[0.25em] mb-2 ${m.role === "user" ? "text-moss-200/70" : "text-amber/90"}`}>
              {m.role === "user" ? "field note" : "house spirit"}
            </div>
            <p className={`font-body whitespace-pre-wrap leading-relaxed ${m.role === "assistant" ? "text-moss-50 text-base" : "text-moss-100"}`}>
              {renderInline(m.text)}
            </p>
          </div>
        ))}
        {busy && (
          <div className="warm-card rounded-2xl p-4 border border-amber/20" data-testid="analysis-loading">
            <div className="text-[10px] uppercase tracking-[0.25em] mb-2 text-amber/90">house spirit</div>
            <p className="text-moss-100 italic">{LOADING_LINES[loadingIndex]}</p>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <ChatInput onSubmit={submit} busy={busy} initialValue={seed} placeholder="Ask what the records suggest." />
    </div>
  );
}
