import { useEffect, useRef, useState } from "react";
import ChatInput from "../components/ChatInput";
import { getChatHistory, sendChat, clearChat } from "../lib/api";
import { renderInline } from "../lib/markdown";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function ConversationPage() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  const load = async () => {
    const d = await getChatHistory();
    setMessages(d.messages || []);
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = async (text, mode) => {
    setBusy(true);
    // optimistic append
    const tempId = "tmp-" + Date.now();
    setMessages(m => [...m, { id: tempId, role: "user", text, mode, timestamp: new Date().toISOString() }]);
    try {
      const res = await sendChat(text, mode);
      setMessages(m => m.filter(x => x.id !== tempId).concat([res.user_msg, res.assistant_msg]));
    } catch (e) {
      setMessages(m => m.filter(x => x.id !== tempId));
      toast("The goblin didn't answer.", { description: e?.response?.data?.detail || "" });
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    if (!window.confirm("Clear the whole conversation? This room forgets.")) return;
    await clearChat();
    setMessages([]);
  };

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-4xl mx-auto" data-testid="conversation-page">
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">The room</div>
          <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Conversation</h1>
        </div>
        <button data-testid="clear-conversation" onClick={clear} className="pill-btn rounded-full px-3 py-1.5 text-xs inline-flex items-center gap-1.5">
          <Trash2 size={13} /> Clear
        </button>
      </div>

      <div className="space-y-6 mb-10" data-testid="messages">
        {messages.length === 0 && (
          <p className="text-moss-200 italic font-body">Empty room. Drop something and we'll start.</p>
        )}
        {messages.map(m => (
          <div key={m.id} className={`rounded-2xl p-5 ${m.role === "user" ? "warm-card" : "warm-card border-amber/30"}`} style={m.role === "assistant" ? { background: "linear-gradient(180deg, rgba(212,163,115,0.10) 0%, rgba(43,47,42,0.85) 100%)" } : undefined}>
            <div className={`text-[10px] uppercase tracking-[0.25em] mb-2 ${m.role === "user" ? "text-moss-200/70" : "text-amber/90"}`}>
              {m.role === "user" ? `you${m.mode && m.mode !== "send" ? ` · ${m.mode.replace("_", " ")}` : ""}` : "the goblin"}
            </div>
            <p className={`font-body whitespace-pre-wrap leading-relaxed ${m.role === "assistant" ? "text-moss-50 font-heading italic text-lg" : "text-moss-100"}`}>
              {renderInline(m.text)}
            </p>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <ChatInput onSubmit={submit} busy={busy} placeholder="Continue. The room is listening." />
    </div>
  );
}
