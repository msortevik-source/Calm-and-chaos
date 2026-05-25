import { useEffect, useState } from "react";
import { Send, Loader2 } from "lucide-react";

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
          placeholder={placeholder || "Ask for patterns, summaries, comparisons, or receipts."}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit("send");
          }}
          rows={compact ? 2 : 3}
        />
        <div className="flex flex-wrap gap-2 mt-3">
          <button
            data-testid="chat-send-button"
            disabled={busy || !text.trim()}
            onClick={() => submit("send")}
            className="pill-btn primary rounded-full px-4 py-1.5 text-xs tracking-wide flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
            Ask
          </button>
        </div>
      </div>
      <div className="text-[11px] text-moss-200/60 mt-2 pl-2 tracking-wide">
        ⌘/Ctrl + Enter to send
      </div>
    </div>
  );
}
