import { useEffect, useState } from "react";
import { createBrainDump } from "../lib/api";
import { Moon, X, Loader2 } from "lucide-react";
import { toast } from "sonner";

// Show only between 21:00 and 02:00 local time
function isEveningHour() {
  const h = new Date().getHours();
  return h >= 21 || h < 2;
}

const todayKey = () => new Date().toISOString().slice(0, 10);
const storageKey = "calm_chaos_evening_dismissed";

export default function EveningCheckin() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    if (!isEveningHour()) return;
    let dismissed = {};
    try { dismissed = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch {}
    if (dismissed[todayKey()]) return;
    setHidden(false);
  }, []);

  if (hidden) return null;

  const dismiss = () => {
    let dismissed = {};
    try { dismissed = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch {}
    dismissed[todayKey()] = true;
    localStorage.setItem(storageKey, JSON.stringify(dismissed));
    setHidden(true);
  };

  const save = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await createBrainDump({ text: text.trim(), tags: ["evening"] });
      toast("Logged. Sleep on it.");
      dismiss();
    } catch {
      toast("Couldn't save that.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-3xl warm-card p-5 animate-fade-up" data-testid="evening-checkin"
      style={{ background: "linear-gradient(180deg, rgba(45, 56, 50, 0.7) 0%, rgba(33, 37, 33, 0.85) 100%)" }}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em]">
          <Moon size={14} /> before bed
        </div>
        <button data-testid="evening-dismiss" onClick={dismiss} className="text-moss-200/60 hover:text-amber transition-colors">
          <X size={14} />
        </button>
      </div>
      <p className="font-heading text-moss-50 text-base md:text-lg italic leading-snug mb-3">
        Anything circling before you close the laptop?
      </p>
      <textarea
        data-testid="evening-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="One sentence is fine. Or skip."
        className="auto-grow w-full bg-moss-800/50 border border-moss-700 rounded-2xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none resize-none focus:border-amber/50 transition-colors"
        rows={2}
      />
      <div className="flex justify-between items-center mt-3">
        <button data-testid="evening-skip" onClick={dismiss} className="text-xs text-moss-200/70 hover:text-amber transition-colors">not tonight</button>
        <button data-testid="evening-save" disabled={busy || !text.trim()} onClick={save} className="pill-btn primary rounded-full px-4 py-1.5 text-xs inline-flex items-center gap-1.5 disabled:opacity-40">
          {busy && <Loader2 size={13} className="animate-spin" />} Tuck it away
        </button>
      </div>
    </div>
  );
}
