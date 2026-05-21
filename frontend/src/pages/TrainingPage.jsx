import { useEffect, useState } from "react";
import { getTemplate, listTraining, createTraining, deleteTraining, MOODS } from "../lib/api";
import DiscussButton from "../components/DiscussButton";
import { Trash2, Activity, Footprints, Dumbbell, NotebookPen } from "lucide-react";
import { toast } from "sonner";

const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function TrainingPage() {
  const [template, setTemplate] = useState({});
  const [entries, setEntries] = useState([]);
  const [kind, setKind] = useState("run");
  const [form, setForm] = useState({ date: todayIso() });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [t, e] = await Promise.all([getTemplate(), listTraining()]);
    setTemplate(t.template || {});
    setEntries(e.entries || []);
  };

  useEffect(() => { load(); }, []);

  const submit = async () => {
    const payload = { kind, ...form };
    if (!payload.date) payload.date = todayIso();
    setBusy(true);
    try {
      await createTraining(payload);
      setForm({ date: todayIso() });
      load();
      toast("Logged.", { description: "Quiet evidence." });
    } catch {
      toast("Couldn't log that.");
    } finally { setBusy(false); }
  };

  const remove = async (id) => {
    await deleteTraining(id);
    load();
  };

  const setField = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-5xl mx-auto" data-testid="training-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Show up. Log it. Move on.</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Training</h1>
      </div>

      <div className="warm-card rounded-3xl p-6 mb-10" data-testid="weekly-template">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-4 flex items-center gap-2">
          <Activity size={14} /> Weekly rhythm
        </div>
        <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
          {DAY_ORDER.map(d => (
            <div key={d} className="rounded-2xl border border-moss-700/60 px-3 py-3 bg-moss-800/30">
              <div className="font-heading text-moss-50 text-sm capitalize">{d.slice(0,3)}</div>
              <div className="text-xs text-moss-200 mt-1 leading-snug">{template[d]?.focus || "—"}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="warm-card rounded-3xl p-6 mb-10" data-testid="training-logger">
        <div className="flex gap-2 mb-5">
          {[
            { id: "run", label: "Run", icon: Footprints },
            { id: "strength", label: "Strength", icon: Dumbbell },
            { id: "note", label: "Note", icon: NotebookPen },
          ].map(k => (
            <button key={k.id} data-testid={`kind-${k.id}`} onClick={() => { setKind(k.id); setForm({ date: todayIso() }); }}
              className={`pill-btn rounded-full px-4 py-1.5 text-xs flex items-center gap-2 ${kind === k.id ? "primary" : ""}`}>
              <k.icon size={13} /> {k.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <input data-testid="training-session-name" placeholder="session name (e.g. 4×4 + upper)" value={form.session_name || ""} onChange={e => setField("session_name", e.target.value)} className={inputCls + " md:col-span-3"} />
          <input type="date" data-testid="training-date" value={form.date || ""} onChange={e => setField("date", e.target.value)} className={inputCls} />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          {kind === "run" && (
            <>
              <input data-testid="training-distance" placeholder="km" type="number" step="0.1" value={form.distance_km || ""} onChange={e => setField("distance_km", parseFloat(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-duration" placeholder="min" type="number" step="0.1" value={form.duration_min || ""} onChange={e => setField("duration_min", parseFloat(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-hr" placeholder="avg HR" type="number" value={form.avg_hr || ""} onChange={e => setField("avg_hr", parseInt(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-pace" placeholder="pace (5:40/km)" value={form.pace || ""} onChange={e => setField("pace", e.target.value)} className={inputCls} />
            </>
          )}
          {kind === "strength" && (
            <>
              <input data-testid="training-exercise" placeholder="exercise" value={form.exercise || ""} onChange={e => setField("exercise", e.target.value)} className={inputCls + " md:col-span-2"} />
              <input data-testid="training-weight" placeholder="kg" type="number" step="0.5" value={form.weight_kg || ""} onChange={e => setField("weight_kg", parseFloat(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-sets" placeholder="sets" type="number" value={form.sets || ""} onChange={e => setField("sets", parseInt(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-reps" placeholder="reps" type="number" value={form.reps || ""} onChange={e => setField("reps", parseInt(e.target.value) || null)} className={inputCls} />
            </>
          )}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <select data-testid="training-mood-before" value={form.mood_before || ""} onChange={e => setField("mood_before", e.target.value)} className={inputCls}>
            <option value="">mood before</option>
            {MOODS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <select data-testid="training-mood-after" value={form.mood_after || ""} onChange={e => setField("mood_after", e.target.value)} className={inputCls}>
            <option value="">mood after</option>
            {MOODS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <input data-testid="training-win" placeholder="win of the day" value={form.win_of_the_day || ""} onChange={e => setField("win_of_the_day", e.target.value)} className={inputCls + " md:col-span-2"} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <textarea data-testid="training-notes" value={form.notes || ""} onChange={e => setField("notes", e.target.value)} placeholder="workout notes" className={inputCls + " min-h-[72px] resize-none"} />
          <textarea data-testid="training-soreness" value={form.soreness_notes || ""} onChange={e => setField("soreness_notes", e.target.value)} placeholder="soreness / body notes" className={inputCls + " min-h-[72px] resize-none"} />
        </div>

        <div className="mt-3 flex justify-end">
          <button data-testid="training-save" disabled={busy} onClick={submit} className="pill-btn primary rounded-full px-5 py-1.5 text-xs disabled:opacity-40">Log it</button>
        </div>
      </div>

      <div className="space-y-3" data-testid="training-entries">
        {entries.length === 0 && <p className="text-moss-200 italic font-body">Nothing logged yet. That's fine.</p>}
        {entries.map(e => (
          <div key={e.id} className="warm-card rounded-2xl p-4 flex items-start gap-4">
            <div className="text-amber font-heading text-sm w-20 shrink-0">{e.date || "—"}</div>
            <div className="flex-1 min-w-0">
              <div className="text-moss-50 text-sm font-medium">
                <span className="capitalize">{e.kind}</span>
                {e.session_name && <span className="text-moss-100"> · {e.session_name}</span>}
                {e.kind === "run" && (e.distance_km || e.duration_min) && (
                  <span className="text-moss-200 font-normal ml-2">
                    {e.distance_km ? `${e.distance_km}km` : ""}{e.duration_min ? ` · ${e.duration_min}min` : ""}{e.pace ? ` · ${e.pace}` : ""}{e.avg_hr ? ` · HR ${e.avg_hr}` : ""}
                  </span>
                )}
                {e.kind === "strength" && (
                  <span className="text-moss-200 font-normal ml-2">
                    {e.exercise || ""}{e.weight_kg ? ` · ${e.weight_kg}kg` : ""}{e.sets && e.reps ? ` · ${e.sets}×${e.reps}` : ""}
                  </span>
                )}
              </div>
              <div className="text-[11px] text-moss-200 mt-1 flex flex-wrap gap-2">
                {e.mood_before && <span>before: <span className="text-amber/90">{e.mood_before}</span></span>}
                {e.mood_after && <span>after: <span className="text-amber/90">{e.mood_after}</span></span>}
                {e.feel ? <span>feel: {e.feel}</span> : null}
              </div>
              {e.win_of_the_day && <p className="text-moss-100 mt-2 font-heading italic text-sm">"{e.win_of_the_day}"</p>}
              {e.notes && <p className="text-moss-200 text-sm mt-1">{e.notes}</p>}
              {e.soreness_notes && <p className="text-moss-200/80 text-xs mt-1">soreness — {e.soreness_notes}</p>}
            </div>
            <div className="flex flex-col gap-2 items-center shrink-0">
              <DiscussButton testid={`training-discuss-${e.id}`} seed={`About this training session on ${e.date || ""}: ${e.session_name || e.kind || ""}${e.kind === "run" && e.distance_km ? ` — ${e.distance_km}km${e.duration_min ? ` in ${e.duration_min}min` : ""}${e.pace ? ` at ${e.pace}` : ""}` : ""}${e.kind === "strength" && e.exercise ? ` — ${e.exercise}${e.weight_kg ? ` ${e.weight_kg}kg` : ""}${e.sets && e.reps ? ` ${e.sets}×${e.reps}` : ""}` : ""}${e.mood_before || e.mood_after ? ` (mood ${e.mood_before || "?"}→${e.mood_after || "?"})` : ""}${e.win_of_the_day ? `. Win: ${e.win_of_the_day}` : ""}${e.notes ? `. Notes: ${e.notes}` : ""}.\n\n`} />
              <button data-testid={`training-delete-${e.id}`} onClick={() => remove(e.id)} className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity">
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
