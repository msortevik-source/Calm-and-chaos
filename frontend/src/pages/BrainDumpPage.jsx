import { useEffect, useState } from "react";
import { listBrainDumps, createBrainDump, deleteBrainDump } from "../lib/api";
import { Trash2, Plus } from "lucide-react";

const fmt = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch { return ""; }
};

export default function BrainDumpPage() {
  const [text, setText] = useState("");
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
      await createBrainDump(text);
      setText("");
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
          Get it out of your head and onto the table. Not for the goblin. Not for me. Just for you.
        </p>
      </div>

      <div className="rounded-3xl border border-moss-700 bg-moss-800/60 p-5">
        <textarea
          data-testid="braindump-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Empty it here..."
          className="auto-grow w-full bg-transparent text-moss-50 placeholder-moss-200/60 outline-none resize-none font-body text-base leading-relaxed"
          rows={4}
        />
        <div className="flex justify-end">
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
          <div key={e.id} className="group rounded-2xl border border-moss-700/70 bg-moss-800/40 p-5 flex gap-4">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-[0.25em] text-moss-200/70 mb-2">{fmt(e.timestamp)}</div>
              <p className="font-body whitespace-pre-wrap leading-relaxed text-moss-100">{e.text}</p>
            </div>
            <button data-testid={`braindump-delete-${e.id}`} onClick={() => remove(e.id)} className="opacity-30 hover:opacity-100 transition-opacity text-moss-200 hover:text-amber self-start">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
