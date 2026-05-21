import { useEffect, useState } from "react";
import { Send, Flame, Anchor, ListTree, Loader2 } from "lucide-react";

const MODES = [
  { id: "send", label: "Send", icon: Send, testid: "chat-send" },
  { id: "hard_truth", label: "Hard truth", icon: Flame, testid: "chat-hard-truth" },
  { id: "ground_me", label: "Ground me", icon: Anchor, testid: "chat-ground-me" },
  { id: "organize", label: "Organize my brain", icon: ListTree, testid: "chat-organize" },
];

export default function ChatInput({ onSubmit, busy, compact = false, placeholder, initialValue = "" }) {
  const [text, setText] = useState(initialValue);

  // When initialValue changes (e.g. arriving via "discuss this"), update the textarea
  useEffect(() => {
    if (initialValue) setText(initialValue);
  }, [initialValue]);

  const submit = async (mode) => {
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    try {
      await onSubmit(t, mode);
    } catch (e) {
      setText(t); // restore
    }
  };

  return (
    <div className="w-full" data-testid="chat-input-container">
      <div className="rounded-3xl warm-card p-4 md:p-5 transition-colors focus-within:border-amber/50">
        <textarea
          data-testid="chat-textarea"
          className="auto-grow w-full bg-transparent text-moss-50 placeholder-moss-200/60 outline-none resize-none font-body text-base leading-relaxed"
          placeholder={placeholder || "Drop it here. No paperwork."}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit("send");
          }}
          rows={compact ? 2 : 3}
        />
        <div className="flex flex-wrap gap-2 mt-3">
          {MODES.map((m) => (
            <button
              key={m.id}
              data-testid={`${m.testid}-button`}
              disabled={busy || !text.trim()}
              onClick={() => submit(m.id)}
              className={`pill-btn ${m.id === "send" ? "primary" : ""} rounded-full px-4 py-1.5 text-xs tracking-wide flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : <m.icon size={13} />}
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="text-[11px] text-moss-200/60 mt-2 pl-2 tracking-wide">
        ⌘/Ctrl + Enter to send
      </div>
    </div>
  );
}
