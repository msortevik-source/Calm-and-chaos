import { useEffect, useState } from "react";
import { listBudget, createBudget, deleteBudget, listMeals, createMeal, deleteMeal, MOODS } from "../lib/api";
import DiscussButton from "../components/DiscussButton";
import { Trash2, Wallet, Soup, Plus } from "lucide-react";
import { toast } from "sonner";

const todayIso = () => new Date().toISOString().slice(0, 10);
const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";

const CATEGORIES = ["food", "transport", "bills", "joy", "regret", "essential", "other"];
const PREP_STATUSES = ["idea", "planned", "prepped", "eaten"];

function BudgetSection() {
  const [entries, setEntries] = useState([]);
  const [monthTotal, setMonthTotal] = useState(0);
  const [byCat, setByCat] = useState({});
  const [form, setForm] = useState({ date: todayIso(), category: "food" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const d = await listBudget();
    setEntries(d.entries || []);
    setMonthTotal(d.month_total || 0);
    setByCat(d.by_category || {});
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.item || !form.amount) { toast("Item and amount, at least."); return; }
    setBusy(true);
    try {
      await createBudget({
        ...form,
        amount: parseFloat(form.amount),
      });
      setForm({ date: todayIso(), category: form.category });
      load();
    } finally { setBusy(false); }
  };

  const setField = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div className="mb-12" data-testid="budget-section">
      <div className="flex items-end justify-between mb-5">
        <div className="flex items-center gap-3">
          <Wallet size={18} className="text-amber" />
          <h2 className="font-heading text-2xl md:text-3xl text-moss-50">Budget</h2>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-[0.25em] text-moss-200/70">this month</div>
          <div className="font-heading text-xl text-moss-50">{monthTotal.toFixed(0)}</div>
        </div>
      </div>

      {Object.keys(byCat).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5" data-testid="budget-bycat">
          {Object.entries(byCat).sort((a,b) => b[1]-a[1]).map(([c, v]) => (
            <div key={c} className="text-xs text-moss-100 bg-moss-800/60 border border-moss-700 rounded-full px-3 py-1">
              {c} · <span className="text-amber">{v.toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="warm-card rounded-3xl p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <input data-testid="budget-item" placeholder="item" value={form.item || ""} onChange={e => setField("item", e.target.value)} className={inputCls + " md:col-span-2"} />
          <input data-testid="budget-amount" placeholder="amount" type="number" step="0.01" value={form.amount || ""} onChange={e => setField("amount", e.target.value)} className={inputCls} />
          <select data-testid="budget-category" value={form.category || "other"} onChange={e => setField("category", e.target.value)} className={inputCls}>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="date" data-testid="budget-date" value={form.date || todayIso()} onChange={e => setField("date", e.target.value)} className={inputCls} />
        </div>
        <textarea data-testid="budget-notes" value={form.notes || ""} onChange={e => setField("notes", e.target.value)} placeholder="notes (optional)" className={inputCls + " w-full mt-3 min-h-[56px] resize-none"} />
        <div className="flex justify-end mt-3">
          <button data-testid="budget-save" disabled={busy || !form.item || !form.amount} onClick={save} className="pill-btn primary rounded-full px-5 py-1.5 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <Plus size={13} /> Add
          </button>
        </div>
      </div>

      <div className="space-y-2" data-testid="budget-entries">
        {entries.length === 0 && <p className="text-moss-200 italic font-body text-sm">No spending yet. Excellent or impossible.</p>}
        {entries.slice(0, 20).map(e => (
          <div key={e.id} className="warm-card rounded-2xl p-4 flex items-center gap-4">
            <div className="text-amber font-heading text-sm w-20 shrink-0">{e.date}</div>
            <div className="flex-1 min-w-0">
              <div className="text-moss-50 text-sm">{e.item}</div>
              {e.notes && <div className="text-moss-200 text-xs italic mt-0.5">{e.notes}</div>}
            </div>
            <div className="text-xs text-moss-200 mr-3 capitalize">{e.category}</div>
            <div className="font-heading text-moss-50 text-base">{Number(e.amount).toFixed(2)}</div>
            <DiscussButton testid={`budget-discuss-${e.id}`} seed={`About this spending: ${e.item} — ${Number(e.amount).toFixed(2)} (${e.category || "other"}) on ${e.date}${e.notes ? `. Notes: ${e.notes}` : ""}.\n\n`} />
            <button data-testid={`budget-delete-${e.id}`} onClick={async () => { await deleteBudget(e.id); load(); }} className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity ml-3">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function MealSection() {
  const [entries, setEntries] = useState([]);
  const [form, setForm] = useState({ date: todayIso(), prep_status: "idea", easy_quick: false });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const d = await listMeals();
    setEntries(d.entries || []);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.meal) { toast("Name the meal at least."); return; }
    setBusy(true);
    try {
      await createMeal(form);
      setForm({ date: todayIso(), prep_status: "idea", easy_quick: false });
      load();
    } finally { setBusy(false); }
  };

  const setField = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div data-testid="meals-section">
      <div className="flex items-center gap-3 mb-5">
        <Soup size={18} className="text-amber" />
        <h2 className="font-heading text-2xl md:text-3xl text-moss-50">Meal planning & prep</h2>
      </div>

      <div className="warm-card rounded-3xl p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <input data-testid="meal-name" placeholder="meal" value={form.meal || ""} onChange={e => setField("meal", e.target.value)} className={inputCls + " md:col-span-2"} />
          <input data-testid="meal-protein" placeholder="protein source" value={form.protein_source || ""} onChange={e => setField("protein_source", e.target.value)} className={inputCls} />
          <select data-testid="meal-status" value={form.prep_status || "idea"} onChange={e => setField("prep_status", e.target.value)} className={inputCls}>
            {PREP_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input type="date" data-testid="meal-date" value={form.date || todayIso()} onChange={e => setField("date", e.target.value)} className={inputCls} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
          <label className="flex items-center gap-2 text-sm text-moss-100 px-3 py-2 rounded-xl border border-moss-700 bg-moss-800/40" data-testid="meal-easy-wrap">
            <input data-testid="meal-easy" type="checkbox" checked={!!form.easy_quick} onChange={e => setField("easy_quick", e.target.checked)} className="accent-amber" />
            easy / quick
          </label>
          <select data-testid="meal-mood" value={form.mood_after || ""} onChange={e => setField("mood_after", e.target.value)} className={inputCls}>
            <option value="">mood after</option>
            {MOODS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <input data-testid="meal-notes" value={form.notes || ""} onChange={e => setField("notes", e.target.value)} placeholder="notes" className={inputCls} />
        </div>
        <div className="flex justify-end mt-3">
          <button data-testid="meal-save" disabled={busy || !form.meal} onClick={save} className="pill-btn primary rounded-full px-5 py-1.5 text-xs inline-flex items-center gap-2 disabled:opacity-40">
            <Plus size={13} /> Add
          </button>
        </div>
      </div>

      <div className="space-y-2" data-testid="meal-entries">
        {entries.length === 0 && <p className="text-moss-200 italic font-body text-sm">No meals logged yet.</p>}
        {entries.slice(0, 20).map(e => (
          <div key={e.id} className="warm-card rounded-2xl p-4 flex items-center gap-4">
            <div className="text-amber font-heading text-sm w-20 shrink-0">{e.date}</div>
            <div className="flex-1 min-w-0">
              <div className="text-moss-50 text-sm">
                {e.meal}
                {e.protein_source && <span className="text-moss-200"> · {e.protein_source}</span>}
                {e.easy_quick && <span className="ml-2 text-[10px] uppercase tracking-wider text-amber/90 bg-amber-soft px-2 py-0.5 rounded-full">easy</span>}
              </div>
              {e.notes && <div className="text-moss-200 text-xs italic mt-0.5">{e.notes}</div>}
            </div>
            <div className="text-xs text-moss-200 mr-2 capitalize">{e.prep_status}</div>
            {e.mood_after && <div className="text-xs text-amber/90 mr-3">{e.mood_after}</div>}
            <DiscussButton testid={`meal-discuss-${e.id}`} seed={`About this meal on ${e.date}: ${e.meal}${e.protein_source ? ` (protein: ${e.protein_source})` : ""}${e.easy_quick ? " — easy/quick" : ""}${e.prep_status ? ` — ${e.prep_status}` : ""}${e.mood_after ? `. Mood after: ${e.mood_after}` : ""}${e.notes ? `. Notes: ${e.notes}` : ""}.\n\n`} />
            <button data-testid={`meal-delete-${e.id}`} onClick={async () => { await deleteMeal(e.id); load(); }} className="opacity-30 hover:opacity-100 text-moss-200 hover:text-amber transition-opacity">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BudgetFoodPage() {
  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-5xl mx-auto" data-testid="budget-food-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Practical. No guilt spiral.</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Budget & food</h1>
        <p className="text-moss-200 mt-3 font-body italic max-w-xl">
          Track it loosely. Notice without lecturing. Protein helps.
        </p>
      </div>
      <BudgetSection />
      <MealSection />
    </div>
  );
}
