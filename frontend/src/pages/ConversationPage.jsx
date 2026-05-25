import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ChatInput from "../components/ChatInput";
import { getChatHistory, sendChat, clearChat } from "../lib/api";
import { renderInline } from "../lib/markdown";
import { CalendarDays, CalendarRange, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function ConversationPage() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
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
      ? "Give me a weekly summary from the app data. Include training completed/missed, Strava runs, gym sessions, food consistency, budget/spending overview, calendar/recovery notes if useful, small pattern observations, and one practical adjustment for next week."
      : "Give me a monthly summary from the app data. Include training sessions, running volume, long-run/easy-run trend, strength progression, budget income/fixed/flexible/category breakdown, food consistency, what quietly improved, main friction point, and one practical adjustment for next month.";
    submit(prompt, "send");
  };

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-4xl mx-auto" data-testid="conversation-page">
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Receipts and patterns</div>
          <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Analysis Corner</h1>
        </div>
        <button data-testid="clear-conversation" onClick={clear} className="pill-btn rounded-full px-3 py-1.5 text-xs inline-flex items-center gap-1.5">
          <Trash2 size={13} /> Clear
        </button>
      </div>

      <div className="warm-card rounded-3xl p-5 mb-8" data-testid="summary-actions">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-3">Summaries</div>
        <div className="flex flex-wrap gap-3">
          <button data-testid="weekly-summary-button" disabled={busy} onClick={() => requestSummary("weekly")} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <CalendarDays size={14} /> Weekly Summary
          </button>
          <button data-testid="monthly-summary-button" disabled={busy} onClick={() => requestSummary("monthly")} className="pill-btn rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <CalendarRange size={14} /> Monthly Summary
          </button>
        </div>
        {summaryPlaceholder && (
          <div className="mt-4 rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4" data-testid={`${summaryPlaceholder}-summary-placeholder`}>
            <div className="text-[10px] uppercase tracking-[0.22em] text-amber/80 mb-2">
              {summaryPlaceholder === "weekly" ? "Weekly Summary" : "Monthly Summary"}
            </div>
            <p className="text-sm text-moss-100 leading-relaxed">
              Placeholder wired. Next pass builds the actual retrieval: training, Strava, budget, food, calendar context, and pattern notes. Receipts first, theatrical nonsense never.
            </p>
          </div>
        )}
      </div>

      <div className="space-y-6 mb-10" data-testid="messages">
        {messages.length === 0 && (
          <p className="text-moss-200 italic font-body">No analysis yet. Ask what changed, what slipped, or where the money went.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`rounded-2xl p-5 ${m.role === "user" ? "warm-card" : "warm-card border-amber/30"}`} style={m.role === "assistant" ? { background: "linear-gradient(180deg, rgba(212,163,115,0.10) 0%, rgba(43,47,42,0.85) 100%)" } : undefined}>
            <div className={`text-[10px] uppercase tracking-[0.25em] mb-2 ${m.role === "user" ? "text-moss-200/70" : "text-amber/90"}`}>
              {m.role === "user" ? "you" : "analysis"}
            </div>
            <p className={`font-body whitespace-pre-wrap leading-relaxed ${m.role === "assistant" ? "text-moss-50 text-base" : "text-moss-100"}`}>
              {renderInline(m.text)}
            </p>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <ChatInput onSubmit={submit} busy={busy} initialValue={seed} placeholder="Ask for patterns, comparisons, or what to adjust next." />
    </div>
  );
}
