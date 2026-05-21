import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Mail, RefreshCw, Loader2 } from "lucide-react";
import { toast } from "sonner";

function renderInline(text) {
  // Convert **bold** to React spans. Returns an array of nodes.
  const parts = [];
  let i = 0;
  const re = /\*\*([^*]+)\*\*/g;
  let m;
  let last = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(<strong key={i++} className="text-moss-50 font-semibold">{m[1]}</strong>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function renderBody(text) {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const trim = line.trim();
    if (!trim) return <div key={i} className="h-2" />;
    const numMatch = trim.match(/^(\d+)[.)]\s+(.+)$/);
    if (numMatch) {
      return (
        <div key={i} className="flex gap-3 text-moss-100">
          <span className="text-amber font-heading shrink-0">{numMatch[1]}.</span>
          <span>{renderInline(numMatch[2])}</span>
        </div>
      );
    }
    if (/^[-*]\s+/.test(trim)) {
      return <div key={i} className="text-moss-100 pl-4 relative before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-amber/70">{renderInline(trim.replace(/^[-*]\s+/, ""))}</div>;
    }
    return <p key={i} className="text-moss-100 leading-relaxed">{renderInline(trim)}</p>;
  });
}

const fmtDate = (iso) => {
  try { return new Date(iso).toLocaleString("en-US", { month: "long", day: "numeric", hour: "numeric", minute: "2-digit" }); } catch { return ""; }
};

export default function LetterPage() {
  const [letters, setLetters] = useState([]);
  const [current, setCurrent] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadArchive = async () => {
    const r = await api.get("/letter/archive?limit=20");
    setLetters(r.data.letters || []);
    if (!current && r.data.letters && r.data.letters.length) {
      setCurrent(r.data.letters[0]);
    }
  };

  const generateOrFetch = async (force = false) => {
    setBusy(true);
    try {
      const r = await api.get(`/letter/current${force ? "?force=true" : ""}`, { timeout: 60000 });
      setCurrent(r.data);
      loadArchive();
    } catch (e) {
      toast("The goblin can't write right now.", { description: e?.response?.data?.detail || "" });
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadArchive();
  }, []);

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-4xl mx-auto" data-testid="letter-page">
      <div className="mb-10 flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2 flex items-center gap-2">
            <Mail size={13} /> Sunday letter
          </div>
          <h1 className="font-heading text-4xl md:text-5xl text-moss-50">From the room</h1>
          <p className="text-moss-200 mt-3 font-body italic max-w-xl">
            A quiet weekly look at what actually happened. Not a report card.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="letter-generate" onClick={() => generateOrFetch(false)} disabled={busy} className="pill-btn primary rounded-full px-4 py-1.5 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />} Write this week
          </button>
          {current && (
            <button data-testid="letter-regenerate" onClick={() => generateOrFetch(true)} disabled={busy} className="pill-btn rounded-full px-3 py-1.5 text-xs inline-flex items-center gap-1.5 disabled:opacity-40">
              <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> Rewrite
            </button>
          )}
        </div>
      </div>

      {!current && !busy && (
        <div className="rounded-3xl warm-card p-8 text-center" data-testid="letter-empty">
          <p className="text-moss-200 italic font-body">No letter yet. Hit "Write this week" when you're ready.</p>
        </div>
      )}

      {current && (
        <article className="rounded-3xl warm-card p-8 md:p-10 mb-10 animate-fade-up" data-testid="letter-current"
          style={{ background: "linear-gradient(180deg, rgba(212,163,115,0.08) 0%, rgba(43,47,42,0.85) 100%)" }}>
          <div className="text-[10px] uppercase tracking-[0.3em] text-amber/90 mb-4">{current.week_key} · {fmtDate(current.generated_at)}</div>
          <div className="space-y-3 font-body text-base md:text-lg">
            {renderBody(current.body)}
          </div>
        </article>
      )}

      {letters.length > 1 && (
        <div className="mt-12" data-testid="letter-archive">
          <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-4">Archive</div>
          <div className="space-y-2">
            {letters.filter(l => !current || l.week_key !== current.week_key).map(l => (
              <button key={l.week_key} onClick={() => setCurrent(l)} className="w-full text-left warm-card rounded-2xl p-4 hover:border-amber/40 transition-colors">
                <div className="text-amber text-xs uppercase tracking-[0.25em]">{l.week_key}</div>
                <div className="text-moss-100 text-sm mt-1 truncate">{(l.body || "").split("\n").filter(Boolean)[0]?.slice(0, 140)}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
