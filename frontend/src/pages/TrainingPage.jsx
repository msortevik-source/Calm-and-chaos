import { useEffect, useState } from "react";
import { getTemplate, listTraining, createTraining, deleteTraining } from "../lib/api";
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
    } catch (e) {
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

      {/* Weekly template */}
      <div className="rounded-3xl border border-moss-700 bg-moss-800/40 p-6 mb-10" data-testid="weekly-template">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-4 flex items-center gap-2">
          <Activity size={14} /> Weekly rhythm
        </div>
        <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
          {DAY_ORDER.map(d => (
            <div key={d} className="rounded-2xl border border-moss-700/60 px-3 py-3">
              <div className="font-heading text-moss-50 text-sm capitalize">{d.slice(0,3)}</div>
              <div className="text-xs text-moss-200 mt-1 leading-snug">{template[d]?.focus || "—"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Logger */}
      <div className="rounded-3xl border border-moss-700 bg-moss-800/60 p-6 mb-10" data-testid="training-logger">
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

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <input type="date" data-testid="training-date" value={form.date || ""} onChange={e => setField("date", e.target.value)} className={inputCls} />

          {kind === "run" && (
            <>
              <input data-testid="training-distance" placeholder="km" type="number" step="0.1" value={form.distance_km || ""} onChange={e => setField("distance_km", parseFloat(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-duration" placeholder="min" type="number" step="0.1" value={form.duration_min || ""} onChange={e => setField("duration_min", parseFloat(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-hr" placeholder="avg HR" type="number" value={form.avg_hr || ""} onChange={e => setField("avg_hr", parseInt(e.target.value) || null)} className={inputCls} />
              <input data-testid="training-pace" placeholder="pace (e.g. 5:40/km)" value={form.pace || ""} onChange={e => setField("pace", e.target.value)} className={inputCls + " md:col-span-2"} />
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

          <select data-testid="training-feel" value={form.feel || ""} onChange={e => setField("feel", parseInt(e.target.value) || null)} className={inputCls}>
            <option value="">feel</option>
            <option value="1">1 — wrecked</option>
            <option value="2">2 — heavy</option>
            <option value="3">3 — ok</option>
            <option value="4">4 — good</option>
            <option value="5">5 — flying</option>
          </select>
        </div>

        <textarea data-testid="training-notes" value={form.notes || ""} onChange={e => setField("notes", e.target.value)} placeholder="notes — terrain, mood, anything" className={inputCls + " w-full min-h-[72px] resize-none"} />

        <div className="mt-4 flex justify-end">
          <button data-testid="training-save" disabled={busy} onClick={submit} className="pill-btn primary rounded-full px-5 py-1.5 text-xs disabled:opacity-40">Log it</button>
        </div>
      </div>

      {/* Entries */}
      <div className="space-y-3" data-testid="training-entries">
        {entries.length === 0 && <p className="text-moss-200 italic font-body">Nothing logged yet. That's fine.</p>}
        {entries.map(e => (
          <div key={e.id} className="rounded-2xl border border-moss-700/70 bg-moss-800/40 p-4 flex items-start gap-4">
            <div className="text-amber font-heading text-sm w-20 shrink-0">{e.date || "—"}</div>
            <div className="flex-1 min-w-0">
              <div className="text-moss-50 text-sm font-medium capitalize">
                {e.kind}
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
                {e.feel ? <span className="text-amber/80 ml-2">· feel {e.feel}</span> : null}
              </div>
              {e.notes && <p className="text-moss-200 text-sm mt-1 italic">{e.notes}</p>}
            </div>
            <button data-testid={`training-delete-${e.id}`} onClick={() => remove(e.id)} className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
