import { useEffect, useState } from "react";
import { listBrainDumps, createBrainDump, deleteBrainDump, MOODS } from "../lib/api";
import DiscussButton from "../components/DiscussButton";
import { Trash2, Plus } from "lucide-react";

const fmt = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch { return ""; }
};

const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";

export default function BrainDumpPage() {
  const [text, setText] = useState("");
  const [energy, setEnergy] = useState("");
  const [mood, setMood] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [entries, setEntries] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const d = await listBrainDumps();
    setEntries(d.entries || []);
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const tags = tagsInput.split(",").map(s => s.trim()).filter(Boolean);
      await createBrainDump({
        text,
        energy: energy ? parseInt(energy) : null,
        mood: mood || null,
        tags: tags.length ? tags : null,
      });
      setText("");
      setTagsInput("");
      setEnergy("");
      setMood("");
      load();
    } finally { setBusy(false); }
  };

  const remove = async (id) => {
    await deleteBrainDump(id);
    load();
  };

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-3xl mx-auto" data-testid="braindump-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">No structure required</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Brain dump</h1>
        <p className="text-moss-200 mt-3 font-body italic max-w-xl">
          Get it out of your head and onto the table. Tag it if you want. Or don't.
        </p>
      </div>

      <div className="warm-card rounded-3xl p-5">
        <textarea
          data-testid="braindump-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Empty it here..."
          className="auto-grow w-full bg-transparent text-moss-50 placeholder-moss-200/60 outline-none resize-none font-body text-base leading-relaxed"
          rows={4}
        />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          <select data-testid="braindump-energy" value={energy} onChange={(e) => setEnergy(e.target.value)} className={inputCls}>
            <option value="">energy</option>
            {[1,2,3,4,5].map(n => <option key={n} value={n}>{n} — {["empty","low","steady","high","wired"][n-1]}</option>)}
          </select>
          <select data-testid="braindump-mood" value={mood} onChange={(e) => setMood(e.target.value)} className={inputCls}>
            <option value="">mood</option>
            {MOODS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <input data-testid="braindump-tags" value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} placeholder="tags, comma, separated" className={inputCls} />
        </div>
        <div className="flex justify-end mt-4">
          <button data-testid="braindump-save" disabled={!text.trim() || busy} onClick={save} className="pill-btn primary rounded-full px-5 py-1.5 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <Plus size={13} /> Drop
          </button>
        </div>
      </div>

      <div className="mt-10 space-y-4" data-testid="braindump-entries">
        {entries.length === 0 && (
          <p className="text-moss-200 italic font-body">The table is empty.</p>
        )}
        {entries.map(e => (
          <div key={e.id} className="group warm-card rounded-2xl p-5 flex gap-4">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-[0.25em] text-moss-200/70 mb-2 flex flex-wrap gap-2 items-center">
                <span>{fmt(e.timestamp)}</span>
                {e.mood && <span className="text-amber">{e.mood}</span>}
                {e.energy && <span>energy {e.energy}</span>}
              </div>
              <p className="font-body whitespace-pre-wrap leading-relaxed text-moss-100">{e.text}</p>
              {e.tags && e.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {e.tags.map(t => <span key={t} className="text-[10px] uppercase tracking-wider text-amber/90 bg-amber-soft px-2 py-0.5 rounded-full">#{t}</span>)}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2 self-start items-center">
              <DiscussButton testid={`braindump-discuss-${e.id}`} seed={`About this brain dump from ${fmt(e.timestamp)}${e.mood ? ` (mood: ${e.mood}${e.energy ? `, energy ${e.energy}` : ""})` : ""}${e.tags && e.tags.length ? ` [tags: ${e.tags.join(", ")}]` : ""}:\n\n"${e.text}"\n\n`} />
              <button data-testid={`braindump-delete-${e.id}`} onClick={() => remove(e.id)} className="opacity-30 hover:opacity-100 transition-opacity text-moss-200 hover:text-amber">
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
