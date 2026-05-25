import { useEffect, useMemo, useRef, useState } from "react";
import {
  getTemplate,
  listTraining,
  createTraining,
  deleteTraining,
  stravaStatus,
  stravaUnlink,
  API,
} from "../lib/api";
import DiscussButton from "../components/DiscussButton";
import { Activity, Dumbbell, Footprints, Link2, RefreshCw, Save, Trash2, Unlink } from "lucide-react";
import { toast } from "sonner";

const DAY_ORDER = ["monday", "wednesday", "friday"];
const SESSION_OPTIONS = [
  { id: "monday", label: "Monday", sub: "Easy run + legs/glutes" },
  { id: "wednesday", label: "Wednesday", sub: "Intervals + upper/core" },
  { id: "friday", label: "Friday", sub: "Easy run + lower/upper" },
  { id: "long", label: "Long run", sub: "Saturday or Sunday" },
];
const LOCAL_TEMPLATE = {
  monday: {
    focus: "Easy Run + Leg / Glute Day",
    run: { label: "Easy run", distance: "3.4 km" },
    exercises: [
      { name: "Hip thrust", sets: 3, reps: 8 },
      { name: "Kickback", sets: 3, reps: 8 },
      { name: "Hip abduction", sets: 3, reps: 8 },
      { name: "Romanian Deadlift (RDL)", sets: 3, reps: 8 },
      { name: "Lateral raises", sets: 3, reps: 8 },
    ],
  },
  wednesday: {
    focus: "Intervals + Upper / Core",
    run: { label: "4x4 intervals" },
    exercises: [
      { name: "Shoulder press", sets: 3, reps: 8 },
      { name: "Triceps", sets: 3, reps: 8 },
      { name: "Bicep curls", sets: 3, reps: 8 },
      { name: "Hammer curls", sets: 3, reps: 8 },
      { name: "Russian twist", sets: 3, reps: 10 },
      { name: "Sit-ups", sets: 3, reps: 10 },
    ],
  },
  friday: {
    focus: "Easy Run + Lower / Upper Mix",
    run: { label: "Easy run", distance: "3-4 km" },
    exercises: [
      { name: "Hip thrust", sets: 3, reps: 8 },
      { name: "Leg press", sets: 3, reps: 8 },
      { name: "Step-ups", sets: 3, reps: 8 },
      { name: "Lateral raises", sets: 3, reps: 8 },
      { name: "Lat pulldown", sets: 3, reps: 8 },
      { name: "Hammer curls", sets: 3, reps: 8 },
      { name: "Russian twist", sets: 3, reps: 10 },
    ],
  },
  saturday: { focus: "Long Run", run: { label: "Long run" }, exercises: [] },
  sunday: { focus: "Long Run", run: { label: "Long run" }, exercises: [] },
};

const todayIso = () => new Date().toISOString().slice(0, 10);
const weekdayKey = () => new Date().toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";

function defaultSession() {
  const day = weekdayKey();
  if (DAY_ORDER.includes(day)) return day;
  if (day === "saturday" || day === "sunday") return "long";
  return "monday";
}

function sessionDay(session, longRunDay) {
  return session === "long" ? longRunDay : session;
}

function lastForExercise(entries, exerciseName) {
  return entries.find((entry) => (
    entry.kind === "strength" &&
    (entry.exercise || "").toLowerCase() === exerciseName.toLowerCase() &&
    (entry.weight_kg || entry.reps)
  ));
}

function lastRun(entries, label) {
  const needle = (label || "").toLowerCase();
  return entries.find((entry) => (
    entry.kind === "run" &&
    (!needle || (entry.session_name || "").toLowerCase().includes(needle.split(" ")[0]))
  ));
}

function ExerciseRow({ exercise, value, previous, onChange }) {
  return (
    <div className="rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
        <div>
          <h3 className="font-heading text-lg text-moss-50">{exercise.name}</h3>
          <p className="text-xs text-moss-200 mt-1">{exercise.sets}x{exercise.reps}</p>
          <p className="text-sm text-moss-200 mt-2">
            Last: {previous ? `${previous.weight_kg || "-"} kg x ${previous.reps || previous.rep_count || "-"}` : "no log yet"}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 w-full md:w-[220px]">
          <input
            type="number"
            step="0.5"
            data-testid={`exercise-weight-${exercise.name}`}
            placeholder="kg"
            value={value.weight_kg ?? ""}
            onChange={(e) => onChange(exercise.name, "weight_kg", e.target.value)}
            className={inputCls}
          />
          <input
            type="number"
            data-testid={`exercise-reps-${exercise.name}`}
            placeholder="reps"
            value={value.reps ?? ""}
            onChange={(e) => onChange(exercise.name, "reps", e.target.value)}
            className={inputCls}
          />
        </div>
      </div>
      <input
        data-testid={`exercise-note-${exercise.name}`}
        placeholder="optional note"
        value={value.notes || ""}
        onChange={(e) => onChange(exercise.name, "notes", e.target.value)}
        className={inputCls + " w-full mt-3"}
      />
    </div>
  );
}

export default function TrainingPage() {
  const workoutRef = useRef(null);
  const entriesRef = useRef(null);
  const [template, setTemplate] = useState(LOCAL_TEMPLATE);
  const [entries, setEntries] = useState([]);
  const [session, setSession] = useState(defaultSession());
  const [longRunDay, setLongRunDay] = useState(weekdayKey() === "sunday" ? "sunday" : "saturday");
  const [date, setDate] = useState(todayIso());
  const [exerciseLog, setExerciseLog] = useState({});
  const [runLog, setRunLog] = useState({});
  const [busy, setBusy] = useState(false);
  const [strava, setStrava] = useState({ configured: true, linked: false });
  const [stravaBusy, setStravaBusy] = useState(false);
  const [stravaImportNote, setStravaImportNote] = useState("");

  const selectedDay = sessionDay(session, longRunDay);
  const workout = useMemo(() => template[selectedDay] || {}, [template, selectedDay]);
  const exercises = useMemo(() => workout.exercises || [], [workout]);
  const run = useMemo(() => workout.run || null, [workout]);

  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => String(b.timestamp || b.date || "").localeCompare(String(a.timestamp || a.date || ""))),
    [entries],
  );

  const load = async () => {
    try {
      const [t, e] = await Promise.all([getTemplate(), listTraining()]);
      setTemplate({ ...LOCAL_TEMPLATE, ...(t.template || {}) });
      setEntries(e.entries || []);
    } catch {
      const t = await getTemplate().catch(() => ({ template: {} }));
      setTemplate({ ...LOCAL_TEMPLATE, ...(t.template || {}) });
      setEntries([]);
    }

    const s = await stravaStatus().catch(() => null);
    if (s) setStrava((prev) => ({ ...s, linked: Boolean(s.linked || prev.linked) }));
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let cleanUrl = false;
    if (params.get("strava") === "linked") {
      setStrava((prev) => ({ ...prev, configured: true, linked: true }));
      toast("Strava linked. Tiny victory parade, very restrained.");
      cleanUrl = true;
    }
    if (params.get("strava") === "error") {
      toast("Strava got weird.", { description: params.get("reason") || "No reason returned. Very helpful, obviously." });
      cleanUrl = true;
    }
    if (params.get("strava_import") === "done") {
      const imported = params.get("imported") || "0";
      const skipped = params.get("skipped") || "0";
      setStrava((prev) => ({ ...prev, configured: true, linked: true }));
      setStravaImportNote(`Imported ${imported}. Skipped ${skipped}.`);
      toast(`Imported ${imported} from Strava.`, {
        description: Number(imported) ? "Training log updated." : "Nothing new. Suspiciously calm.",
      });
      window.setTimeout(() => {
        entriesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 250);
      cleanUrl = true;
    }
    if (params.get("strava_import") === "error") {
      const reason = params.get("reason") || "import_failed";
      setStravaImportNote(`Import failed: ${reason}`);
      toast("Couldn't import Strava activities.", { description: reason });
      cleanUrl = true;
    }
    if (cleanUrl) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    load();
  }, []);

  useEffect(() => {
    const next = {};
    exercises.forEach((exercise) => {
      const last = lastForExercise(sortedEntries, exercise.name);
      next[exercise.name] = {
        weight_kg: last?.weight_kg || "",
        reps: last?.reps || exercise.reps || "",
        notes: "",
      };
    });
    setExerciseLog(next);

    if (run) {
      const last = lastRun(sortedEntries, run.label);
      setRunLog({
        distance_km: last?.distance_km || "",
        duration_min: last?.duration_min || "",
        notes: "",
      });
    } else {
      setRunLog({});
    }
  }, [selectedDay, exercises, run, sortedEntries]);

  const setExerciseField = (name, key, rawValue) => {
    setExerciseLog((prev) => ({
      ...prev,
      [name]: { ...prev[name], [key]: rawValue },
    }));
  };

  const chooseSession = (nextSession) => {
    setSession(nextSession);
    window.setTimeout(() => {
      workoutRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
  };

  const saveWorkout = async () => {
    setBusy(true);
    try {
      const tasks = [];
      if (run && (runLog.distance_km || runLog.duration_min || runLog.notes || run.distance)) {
        tasks.push(createTraining({
          kind: "run",
          date,
          session_name: run.label,
          distance_km: runLog.distance_km ? Number(runLog.distance_km) : null,
          duration_min: runLog.duration_min ? Number(runLog.duration_min) : null,
          notes: runLog.notes || "",
        }));
      }

      exercises.forEach((exercise) => {
        const value = exerciseLog[exercise.name] || {};
        if (!value.weight_kg && !value.reps && !value.notes) return;
        tasks.push(createTraining({
          kind: "strength",
          date,
          session_name: workout.focus,
          exercise: exercise.name,
          sets: exercise.sets,
          reps: value.reps ? Number(value.reps) : exercise.reps,
          weight_kg: value.weight_kg ? Number(value.weight_kg) : null,
          notes: value.notes || "",
        }));
      });

      if (!tasks.length) {
        toast("Nothing to save. The workout is prepared, not psychic.");
        return;
      }

      await Promise.all(tasks);
      await load();
      toast("Saved.", { description: "Continue, not start over." });
    } catch {
      toast("Couldn't save workout.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      await deleteTraining(id);
      load();
    } catch {
      toast("Couldn't delete that.");
    }
  };

  const linkStrava = async () => {
    setStravaBusy(true);
    window.location.href = `${API}/oauth/strava/login?redirect=true`;
  };

  const importStrava = async () => {
    setStravaBusy(true);
    setStravaImportNote("Importing recent activities...");
    window.location.href = `${API}/strava/import/recent?limit=10&redirect=true`;
  };

  const unlinkStrava = async () => {
    setStravaBusy(true);
    try {
      await stravaUnlink();
      setStrava((prev) => ({ ...prev, linked: false, athlete: null }));
      await load();
      toast("Strava unlinked.");
    } catch {
      toast("Couldn't unlink Strava.");
    } finally {
      setStravaBusy(false);
    }
  };

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-6xl mx-auto" data-testid="training-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Future me already prepared this</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Training</h1>
      </div>

      <div className="warm-card rounded-3xl p-6 mb-8" data-testid="weekly-template">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-4 flex items-center gap-2">
          <Activity size={14} /> Choose session
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SESSION_OPTIONS.map((option) => (
            <button
              key={option.id}
              data-testid={`session-${option.id}`}
              onClick={() => chooseSession(option.id)}
              className={`text-left rounded-2xl border px-4 py-3 transition-colors ${session === option.id ? "border-amber bg-amber/10" : "border-moss-700/60 bg-moss-800/30 hover:border-moss-500"}`}
            >
              <div className="font-heading text-moss-50 text-sm">{option.label}</div>
              <div className="text-xs text-moss-200 mt-1 leading-snug">{option.sub}</div>
              {session === option.id && <div className="text-[10px] uppercase tracking-[0.18em] text-amber mt-3">Logging below</div>}
            </button>
          ))}
        </div>
      </div>

      <div ref={workoutRef} className="warm-card rounded-3xl p-6 mb-8 scroll-mt-32" data-testid="prepared-workout">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-5">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2 flex items-center gap-2">
              <Dumbbell size={14} /> Prepared session
            </div>
            <h2 className="font-heading text-3xl text-moss-50">{workout.focus || "Prepared workout"}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {session === "long" && (
              <select data-testid="long-run-day" value={longRunDay} onChange={(e) => setLongRunDay(e.target.value)} className={inputCls}>
                <option value="saturday">Saturday</option>
                <option value="sunday">Sunday</option>
              </select>
            )}
            <input data-testid="training-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
          </div>
        </div>

        {run && (
          <div className="rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
              <Footprints size={15} className="text-amber" />
              <div>
                <h3 className="font-heading text-lg text-moss-50">{run.label}</h3>
                {run.distance && <p className="text-xs text-moss-200">{run.distance}</p>}
              </div>
            </div>
            <p className="text-sm text-moss-200 mb-3">
              Last: {lastRun(sortedEntries, run.label) ? `${lastRun(sortedEntries, run.label)?.distance_km || "-"} km x ${lastRun(sortedEntries, run.label)?.duration_min || "-"} min` : "no log yet"}
            </p>
            <div className="grid md:grid-cols-3 gap-2">
              <input data-testid="run-distance" type="number" step="0.1" placeholder="distance km" value={runLog.distance_km || ""} onChange={(e) => setRunLog((p) => ({ ...p, distance_km: e.target.value }))} className={inputCls} />
              <input data-testid="run-time" type="number" step="0.1" placeholder="time min" value={runLog.duration_min || ""} onChange={(e) => setRunLog((p) => ({ ...p, duration_min: e.target.value }))} className={inputCls} />
              <input data-testid="run-notes" placeholder="optional notes" value={runLog.notes || ""} onChange={(e) => setRunLog((p) => ({ ...p, notes: e.target.value }))} className={inputCls} />
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-2 gap-3">
          {exercises.map((exercise) => (
            <ExerciseRow
              key={exercise.name}
              exercise={exercise}
              value={exerciseLog[exercise.name] || {}}
              previous={lastForExercise(sortedEntries, exercise.name)}
              onChange={setExerciseField}
            />
          ))}
        </div>

        <div className="mt-5 flex justify-end">
          <button data-testid="training-save" disabled={busy} onClick={saveWorkout} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <Save size={13} /> Save session
          </button>
        </div>
      </div>

      <div className="warm-card rounded-3xl p-6 mb-10" data-testid="strava-card">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2 flex items-center gap-2">
              <Activity size={14} /> Strava
            </div>
            <h2 className="font-heading text-2xl text-moss-50">{strava.linked ? "Connected" : "Connect runs"}</h2>
            <p className="text-sm text-moss-200 mt-1">
              {strava.linked
                ? `Linked${strava.athlete?.firstname ? ` as ${strava.athlete.firstname}` : ""}. Import recent activities when you want the log caught up.`
                : "Pull recent activities into training without manually typing every kilometer like it is 2009."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!strava.linked && (
              <button data-testid="strava-link" disabled={stravaBusy} onClick={linkStrava} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
                <Link2 size={13} /> Link Strava
              </button>
            )}
            {strava.linked && (
              <>
                <button data-testid="strava-import" disabled={stravaBusy} onClick={importStrava} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
                  <RefreshCw size={13} className={stravaBusy ? "animate-spin" : ""} /> {stravaBusy ? "Importing" : "Import recent"}
                </button>
                <button data-testid="strava-unlink" disabled={stravaBusy} onClick={unlinkStrava} className="pill-btn rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 disabled:opacity-40">
                  <Unlink size={13} /> Unlink
                </button>
              </>
            )}
          </div>
          {stravaImportNote && <p className="text-xs text-moss-200 mt-3 md:text-right">{stravaImportNote}</p>}
        </div>
      </div>

      <div ref={entriesRef} className="space-y-3 scroll-mt-32" data-testid="training-entries">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Receipts</div>
            <h2 className="font-heading text-3xl text-moss-50">Training log</h2>
          </div>
          <div className="text-xs text-moss-200">{entries.length} saved</div>
        </div>
        {entries.length === 0 && (
          <div className="warm-card rounded-2xl p-4 text-sm text-moss-200">
            No training entries visible yet.
          </div>
        )}
        {entries.slice(0, 16).map((entry) => (
          <div key={entry.id} className="warm-card rounded-2xl p-4 flex items-start gap-4">
            <div className="text-amber font-heading text-sm w-20 shrink-0">{entry.date || "-"}</div>
            <div className="flex-1 min-w-0">
              <div className="text-moss-50 text-sm font-medium">
                <span className="capitalize">{entry.kind}</span>
                {entry.session_name && <span className="text-moss-100"> - {entry.session_name}</span>}
                {entry.kind === "run" && (entry.distance_km || entry.duration_min) && (
                  <span className="text-moss-200 font-normal ml-2">
                    {entry.distance_km ? `${entry.distance_km}km` : ""}{entry.duration_min ? ` - ${entry.duration_min}min` : ""}{entry.pace ? ` - ${entry.pace}` : ""}{entry.avg_hr ? ` - HR ${entry.avg_hr}` : ""}
                  </span>
                )}
                {entry.kind === "strength" && (
                  <span className="text-moss-200 font-normal ml-2">
                    {entry.exercise || ""}{entry.weight_kg ? ` - ${entry.weight_kg}kg` : ""}{entry.sets && entry.reps ? ` - ${entry.sets}x${entry.reps}` : ""}
                  </span>
                )}
              </div>
              {entry.notes && <p className="text-moss-200 text-sm mt-1">{entry.notes}</p>}
            </div>
            <div className="flex flex-col gap-2 items-center shrink-0">
              <DiscussButton testid={`training-discuss-${entry.id}`} seed={`About this training session on ${entry.date || ""}: ${entry.session_name || entry.kind || ""}${entry.kind === "run" && entry.distance_km ? ` - ${entry.distance_km}km${entry.duration_min ? ` in ${entry.duration_min}min` : ""}${entry.pace ? ` at ${entry.pace}` : ""}` : ""}${entry.kind === "strength" && entry.exercise ? ` - ${entry.exercise}${entry.weight_kg ? ` ${entry.weight_kg}kg` : ""}${entry.sets && entry.reps ? ` ${entry.sets}x${entry.reps}` : ""}` : ""}${entry.notes ? `. Notes: ${entry.notes}` : ""}.\n\n`} />
              <button data-testid={`training-delete-${entry.id}`} onClick={() => remove(entry.id)} className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity">
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
