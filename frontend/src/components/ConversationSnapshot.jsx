import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { getChatRecent } from "../lib/api";

export default function ConversationSnapshot({ refreshKey }) {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    getChatRecent().then(d => setMessages(d.messages || [])).catch(() => {});
  }, [refreshKey]);

  if (messages.length === 0) {
    return (
      <div className="rounded-3xl warm-card p-6" data-testid="conversation-snapshot">
        <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em] mb-3">
          <MessageCircle size={14} /> Last said
        </div>
        <p className="text-moss-200 font-body italic text-sm">
          Nothing recent. Drop a thought below and we'll see where it goes.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-3xl warm-card p-6" data-testid="conversation-snapshot">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em]">
          <MessageCircle size={14} /> Last said
        </div>
        <Link to="/conversation" className="text-amber text-xs hover:underline" data-testid="snapshot-open-conv">open</Link>
      </div>
      <div className="space-y-4">
        {messages.map(m => (
          <div key={m.id}>
            <div className={`text-[10px] uppercase tracking-[0.2em] mb-1 ${m.role === "user" ? "text-moss-200/70" : "text-amber/80"}`}>
              {m.role === "user" ? "you" : "the goblin"}
            </div>
            <p className={`font-body text-sm leading-relaxed ${m.role === "assistant" ? "text-moss-50 font-heading italic" : "text-moss-100"}`}>
              {m.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
