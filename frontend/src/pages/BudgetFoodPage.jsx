import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, CalendarDays, Check, ListChecks, Plus, ShoppingBasket, Trash2, Utensils, Wallet } from "lucide-react";
import { toast } from "sonner";
import {
  archiveBudgetCycle,
  createSpending,
  deleteSpending,
  getBudgetV1,
  getFoodV1,
  listBudgetArchives,
  markSpendingCheckin,
  saveBudgetSetup,
  saveFoodV1,
  BUILD_MARKER,
} from "../lib/api";

const todayIso = () => new Date().toISOString().slice(0, 10);
const cycleKeyForDate = (iso = todayIso()) => {
  const date = new Date(`${iso}T12:00:00`);
  if (date.getDate() < 12) date.setMonth(date.getMonth() - 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
};
const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";
const FALLBACK_SPENDING_CATEGORIES = ["groceries", "snus", "Monster / energy drink", "candy / snacks", "takeaway", "coffee", "transport", "random nonsense", "other"];
const FALLBACK_LUNCH_OPTIONS = ["protein lunch bowls", "rice bowls", "wraps", "pasta salad", "egg/potato plates"];
const FALLBACK_PROTEIN_OPTIONS = ["chicken", "salmon", "minced meat", "pork", "eggs", "yoghurt/kesam/skyr", "cottage cheese"];
const FALLBACK_BUDGET_FEELINGS = ["normal", "tighter", "treat week"];

const money = (value, decimals = 0) => {
  const amount = Number(value || 0);
  return `${new Intl.NumberFormat("nb-NO", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount)} kr`;
};

function Stat({ label, value }) {
  return (
    <div className="warm-card rounded-2xl p-4">
      <div className="text-[10px] uppercase tracking-[0.22em] text-moss-200/70 mb-1">{label}</div>
      <div className="font-heading text-2xl text-moss-50">{value}</div>
    </div>
  );
}

function BudgetV1() {
  const [cycle, setCycle] = useState(cycleKeyForDate());
  const [data, setData] = useState(null);
  const [archives, setArchives] = useState([]);
  const [setup, setSetup] = useState({ income: {}, fixed_expenses: {} });
  const [spend, setSpend] = useState({ date: todayIso(), category: "groceries" });
  const [busy, setBusy] = useState(false);
  const [newIncome, setNewIncome] = useState("");
  const [newExpense, setNewExpense] = useState("");

  const load = useCallback(async () => {
    const [res, archiveRes] = await Promise.all([getBudgetV1(cycle), listBudgetArchives()]);
    setData(res);
    setArchives(archiveRes.archives || []);
    setSetup(res.setup || { income: {}, fixed_expenses: {} });
  }, [cycle]);

  useEffect(() => { load().catch(() => toast("Budget is being dramatic.")); }, [load]);

  const setMoney = (group, key, value) => {
    setSetup((prev) => ({ ...prev, [group]: { ...prev[group], [key]: value } }));
  };

  const setNote = (group, key, value) => {
    setSetup((prev) => ({ ...prev, [group]: { ...(prev[group] || {}), [key]: value } }));
  };

  const setFixedActive = (key, checked) => {
    setSetup((prev) => ({
      ...prev,
      fixed_active: { ...(prev.fixed_active || {}), [key]: checked },
    }));
  };

  const addSetupKey = (group, name, clear) => {
    const key = name.trim();
    if (!key) return;
    setSetup((prev) => {
      const next = { ...prev, [group]: { ...(prev[group] || {}), [key]: 0 } };
      if (group === "fixed_expenses") {
        next.fixed_active = { ...(prev.fixed_active || {}), [key]: true };
      }
      return next;
    });
    clear("");
  };

  const saveSetup = async () => {
    setBusy(true);
    try {
      await saveBudgetSetup({
        month: cycle,
        income: setup.income,
        income_notes: setup.income_notes || {},
        fixed_expenses: setup.fixed_expenses,
        fixed_notes: setup.fixed_notes || {},
        fixed_active: setup.fixed_active || {},
      });
      await load();
      toast("Cycle saved. Future you gets a chair.");
    } catch (e) {
      toast("Cycle did not save.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const addSpending = async () => {
    if (!spend.amount) { toast("Amount first. One number. Very rude, very necessary."); return; }
    setBusy(true);
    try {
      await createSpending({ ...spend, amount: Number(spend.amount) });
      setSpend({ date: todayIso(), category: spend.category });
      await load();
      toast("Logged. It should show up everywhere now.");
    } catch (e) {
      toast("Spending did not save.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const checkInNoSpend = async () => {
    setBusy(true);
    try {
      await markSpendingCheckin({ date: spend.date || todayIso() });
      await load();
      toast("Noted. Zero-spend days still count as noticing.");
    } catch (e) {
      toast("Check-in did not save.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const archiveCurrentCycle = async () => {
    setBusy(true);
    try {
      await saveBudgetSetup({
        month: cycle,
        income: setup.income,
        income_notes: setup.income_notes || {},
        fixed_expenses: setup.fixed_expenses,
        fixed_notes: setup.fixed_notes || {},
        fixed_active: setup.fixed_active || {},
      });
      const res = await archiveBudgetCycle({ cycle });
      if (res.archive) {
        setArchives((prev) => [
          res.archive,
          ...prev.filter((item) => item.cycle_key !== res.archive.cycle_key),
        ]);
      }
      await load();
      toast("Cycle archived. Receipts are in the drawer.");
    } catch (e) {
      toast("Cycle did not archive.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const summary = data?.summary || {};
  const cycleInfo = data?.cycle || summary.cycle || {};
  const spendingCategories = data?.categories?.length ? data.categories : FALLBACK_SPENDING_CATEGORIES;
  const groupedSpending = useMemo(() => {
    const groups = {};
    (data?.spending || []).forEach((entry) => {
      const category = entry.category || "other";
      if (!groups[category]) groups[category] = { total: 0, entries: [] };
      groups[category].total += Number(entry.amount || 0);
      groups[category].entries.push(entry);
    });
    return Object.entries(groups).sort((a, b) => b[1].total - a[1].total);
  }, [data?.spending]);
  const incomeEntries = Object.entries(setup.income || {});
  const fixedEntries = Object.entries(setup.fixed_expenses || {});
  const fixedActive = setup.fixed_active || summary.fixed_active || {};
  const incomeNotes = setup.income_notes || {};
  const fixedNotes = setup.fixed_notes || {};
  const resetWindow = "12th to 11th";

  return (
    <section className="space-y-6" data-testid="budget-v1">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em] mb-2">
            <Wallet size={14} /> Household ledger
          </div>
          <h2 className="font-heading text-3xl text-moss-50">Ledger Period</h2>
        </div>
        <div className="flex flex-col items-start md:items-end gap-2">
          <input data-testid="budget-month" type="month" value={cycle} onChange={(e) => setCycle(e.target.value)} className={inputCls + " w-44"} />
          <div className="text-xs text-moss-200">Cycle: {cycleInfo.label || "12th - 11th"}</div>
          <div className="text-[10px] text-moss-200/50">{BUILD_MARKER}</div>
        </div>
      </div>

      <div className="warm-card rounded-2xl p-4" data-testid="monthly-snapshot">
        <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-2">ledger overview</div>
        <div className="font-heading text-xl text-moss-50 mb-2">{cycleInfo.label || summary.cycle_label || "Current salary cycle"}</div>
        <div className="text-sm md:text-base text-moss-50 leading-relaxed">
          Income: <span className="text-amber">{money(summary.income_total)}</span>
          <span className="text-moss-200"> | </span>
          Fixed: <span className="text-amber">{money(summary.fixed_total)}</span>
          <span className="text-moss-200"> | </span>
          Flexible logged: <span className="text-amber">{money(summary.flexible_total)}</span>
          <span className="text-moss-200"> | </span>
          Expected left: <span className="text-amber">{money(summary.left_after_logged_spending)}</span>
        </div>
      </div>

      <div className="grid md:grid-cols-4 gap-3">
        <Stat label="income" value={money(summary.income_total)} />
        <Stat label="active fixed" value={money(summary.fixed_total)} />
        <Stat label="flexible logged" value={money(summary.flexible_total)} />
        <Stat label="expected left" value={money(summary.left_after_logged_spending)} />
      </div>
      <div className="warm-card rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-moss-200/70">ledger reset</div>
          <div className="text-sm text-moss-100">{resetWindow}: new cycle, same labels, fresh amounts and logs.</div>
        </div>
        <div className="font-heading text-xl text-moss-50">{summary.checked_days || 0}/{summary.days_in_cycle || summary.days_in_month || 31} days checked in</div>
      </div>
      <div className="warm-card rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-moss-200/70">ledger shelf</div>
          <div className="text-sm text-moss-100">Store this period as an old ledger book for later comparison.</div>
        </div>
        <button data-testid="budget-archive-current" disabled={busy} onClick={archiveCurrentCycle} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2">
          <Archive size={13} /> Store ledger period
        </button>
      </div>

      <div className="grid xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.85fr)] gap-5 items-start">
        <div className="warm-card rounded-3xl p-5">
          <h3 className="font-heading text-xl text-moss-50 mb-4">Ledger entries</h3>
          <div className="grid xl:grid-cols-2 gap-5">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-3">income</div>
              <div className="space-y-2">
                {incomeEntries.map(([key, value]) => (
                  <label key={key} className="grid grid-cols-1 sm:grid-cols-[1fr_110px] 2xl:grid-cols-[1fr_110px_150px] gap-2 items-center text-sm text-moss-100">
                    <span>{key}</span>
                    <input type="number" value={value || ""} onChange={(e) => setMoney("income", key, e.target.value)} className={inputCls} />
                    <input value={incomeNotes[key] || ""} onChange={(e) => setNote("income_notes", key, e.target.value)} placeholder="note" className={inputCls} />
                  </label>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input value={newIncome} onChange={(e) => setNewIncome(e.target.value)} placeholder="custom income source" className={inputCls + " flex-1"} />
                <button type="button" onClick={() => addSetupKey("income", newIncome, setNewIncome)} className="pill-btn rounded-full px-3 py-2 text-xs">Add</button>
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-3">fixed expenses</div>
              <div className="space-y-2 max-h-[340px] overflow-auto pr-1">
                {fixedEntries.map(([key, value]) => (
                  <label key={key} className="grid grid-cols-[auto_1fr] sm:grid-cols-[auto_1fr_110px] 2xl:grid-cols-[auto_1fr_110px_150px] gap-2 items-center text-sm text-moss-100">
                    <input type="checkbox" checked={fixedActive[key] !== false} onChange={(e) => setFixedActive(key, e.target.checked)} />
                    <span className={fixedActive[key] === false ? "text-moss-200/50 line-through" : ""}>{key}</span>
                    <input type="number" value={value || ""} onChange={(e) => setMoney("fixed_expenses", key, e.target.value)} className={inputCls} />
                    <input value={fixedNotes[key] || ""} onChange={(e) => setNote("fixed_notes", key, e.target.value)} placeholder="note" className={inputCls} />
                  </label>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                <input value={newExpense} onChange={(e) => setNewExpense(e.target.value)} placeholder="custom recurring expense" className={inputCls + " flex-1"} />
                <button type="button" onClick={() => addSetupKey("fixed_expenses", newExpense, setNewExpense)} className="pill-btn rounded-full px-3 py-2 text-xs">Add</button>
              </div>
            </div>
          </div>
          <button data-testid="budget-setup-save" disabled={busy} onClick={saveSetup} className="pill-btn primary rounded-full px-5 py-2 text-xs mt-5">
            Save cycle
          </button>
        </div>

        <div className="warm-card rounded-3xl p-4 xl:max-w-[380px] xl:justify-self-end w-full">
          <div className="flex items-center gap-2 mb-4">
            <ListChecks size={15} className="text-amber" />
            <h3 className="font-heading text-xl text-moss-50">Anything spent today?</h3>
          </div>
          <div className="grid grid-cols-1 gap-2">
            <input data-testid="spending-amount" type="number" step="0.01" placeholder="amount in kr" value={spend.amount || ""} onChange={(e) => setSpend((p) => ({ ...p, amount: e.target.value }))} className={inputCls} />
            <select data-testid="spending-category" value={spend.category} onChange={(e) => setSpend((p) => ({ ...p, category: e.target.value }))} className={inputCls}>
              {spendingCategories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
            </select>
            <input data-testid="spending-date" type="date" value={spend.date} onChange={(e) => setSpend((p) => ({ ...p, date: e.target.value }))} className={inputCls} />
            <input data-testid="spending-note" placeholder="note, if useful" value={spend.note || ""} onChange={(e) => setSpend((p) => ({ ...p, note: e.target.value }))} className={inputCls} />
          </div>
          <div className="flex flex-wrap gap-2 mt-4">
            <button data-testid="spending-save" disabled={busy} onClick={addSpending} className="pill-btn primary rounded-full px-4 py-2 text-xs inline-flex items-center gap-2">
              <Plus size={13} /> Log it
            </button>
            <button data-testid="spending-checkin" disabled={busy} onClick={checkInNoSpend} className="pill-btn rounded-full px-4 py-2 text-xs inline-flex items-center gap-2">
              <Check size={13} /> Nothing spent
            </button>
          </div>

          <div className="mt-6">
            <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-3">categories</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(summary.by_category || {}).map(([cat, amount]) => (
                <span key={cat} className="rounded-full border border-moss-700 bg-moss-800/50 px-3 py-1 text-xs text-moss-100">
                  {cat}: <span className="text-amber">{money(amount)}</span>
                </span>
              ))}
              {Object.keys(summary.by_category || {}).length === 0 && <span className="text-sm text-moss-200 italic">No spend logged. Either peaceful or undocumented.</span>}
            </div>
          </div>

          {(summary.observations || []).length > 0 && (
            <div className="mt-5 space-y-2">
              {summary.observations.map((obs) => <p key={obs} className="text-sm text-moss-200 italic">{obs}</p>)}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2" data-testid="spending-list">
        {groupedSpending.length > 0 && (
          <div className="warm-card rounded-3xl p-5 mb-4" data-testid="spending-category-overview">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-2 mb-4">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70">ledger tabs</div>
                <div className="text-sm text-moss-200 mt-1">Tap a category when you want the receipt pile. Otherwise it can sit quietly.</div>
              </div>
              <div className="font-heading text-xl text-amber">{money(summary.flexible_total)}</div>
            </div>
            <div className="space-y-2">
              {groupedSpending.map(([category, group]) => (
                <details key={category} className="rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4">
                  <summary className="cursor-pointer list-none">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-heading text-lg text-moss-50">{category}</div>
                        <div className="text-xs text-moss-200">{group.entries.length} entries</div>
                      </div>
                      <div className="text-amber font-heading">{money(group.total)}</div>
                    </div>
                  </summary>
                  <div className="space-y-1 mt-3 border-t border-moss-700/60 pt-3">
                    {group.entries.map((entry) => (
                      <div key={entry.id} className="flex items-center justify-between gap-3 text-sm text-moss-100">
                        <span className="truncate">{entry.date}{entry.note ? ` - ${entry.note}` : ""}</span>
                        <span className="text-moss-50 shrink-0">{money(entry.amount, 2)}</span>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}
        {(data?.spending || []).length > 0 && (
          <details className="warm-card rounded-2xl p-4">
            <summary className="cursor-pointer list-none">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-heading text-lg text-moss-50">Recent entries</div>
                  <div className="text-xs text-moss-200">Last {Math.min((data?.spending || []).length, 12)} logs</div>
                </div>
                <div className="text-xs uppercase tracking-[0.18em] text-amber">open</div>
              </div>
            </summary>
            <div className="space-y-2 mt-3 border-t border-moss-700/60 pt-3">
              {(data?.spending || []).slice(0, 12).map((entry) => (
                <div key={entry.id} className="flex items-center gap-3">
                  <div className="text-amber font-heading text-sm w-24 shrink-0">{entry.date}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-moss-50 text-sm">{entry.category}</div>
                    {entry.note && <div className="text-moss-200 text-xs italic">{entry.note}</div>}
                  </div>
                  <div className="font-heading text-moss-50">{money(entry.amount, 2)}</div>
                  <button data-testid={`spending-delete-${entry.id}`} onClick={async () => { await deleteSpending(entry.id); load(); }} className="text-moss-200/50 hover:text-amber">
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>

      <div className="warm-card rounded-3xl p-5" data-testid="budget-cycle-archive">
        <div className="flex items-center gap-2 mb-4">
          <Archive size={16} className="text-amber" />
          <h3 className="font-heading text-2xl text-moss-50">Old Ledger Books</h3>
        </div>
        <div className="space-y-3">
          {archives.length === 0 && (
            <p className="text-sm text-moss-200 italic">No archived cycles yet. The drawer is empty, suspiciously innocent.</p>
          )}
          {archives.map((archive) => {
            const archiveSummary = archive.summary || {};
            const archiveCategories = archive.categories || archiveSummary.by_category || {};
            const archiveSpending = archive.spending || [];
            return (
              <details key={archive.cycle_key || archive.id} className="rounded-2xl border border-moss-700/70 bg-moss-800/35 p-4">
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                    <div>
                      <div className="font-heading text-xl text-moss-50">{archive.cycle_name || archiveSummary.cycle_label || archive.cycle_key}</div>
                      <div className="text-xs text-moss-200">{archive.start_date} - {archive.end_date}</div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-moss-100">
                      <span>Income <b className="text-amber">{money(archiveSummary.income_total)}</b></span>
                      <span>Fixed <b className="text-amber">{money(archiveSummary.fixed_total)}</b></span>
                      <span>Flexible <b className="text-amber">{money(archiveSummary.flexible_total)}</b></span>
                      <span>Left <b className="text-amber">{money(archiveSummary.left_after_logged_spending)}</b></span>
                    </div>
                  </div>
                </summary>
                <div className="mt-4 grid lg:grid-cols-[0.8fr_1.2fr] gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-2">categories</div>
                    <div className="space-y-1">
                      {Object.entries(archiveCategories).map(([cat, amount]) => (
                        <div key={cat} className="flex items-center justify-between gap-3 text-sm text-moss-100">
                          <span>{cat}</span>
                          <span className="text-amber">{money(amount)}</span>
                        </div>
                      ))}
                      {Object.keys(archiveCategories).length === 0 && <div className="text-sm text-moss-200 italic">No flexible spending logged.</div>}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-2">entries</div>
                    <div className="max-h-72 overflow-auto space-y-1 pr-1">
                      {archiveSpending.map((entry) => (
                        <div key={entry.id} className="grid grid-cols-[82px_1fr_auto] gap-2 text-sm text-moss-100">
                          <span className="text-amber">{entry.date}</span>
                          <span className="truncate">{entry.category}{entry.note ? ` - ${entry.note}` : ""}</span>
                          <span className="text-moss-50">{money(entry.amount, 2)}</span>
                        </div>
                      ))}
                      {archiveSpending.length === 0 && <div className="text-sm text-moss-200 italic">No entries in this cycle.</div>}
                    </div>
                  </div>
                </div>
              </details>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FoodV1() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [autoPlanning, setAutoPlanning] = useState(false);

  const load = async () => {
    const res = await getFoodV1();
    setData(res);
    setForm(res.plan?.inputs || {});
  };

  useEffect(() => { load().catch(() => toast("Food plan refused to assemble itself.")); }, []);

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const setFieldAndRegenerate = (key, value) => {
    let nextForm = null;
    setForm((prev) => {
      nextForm = { ...prev, [key]: value };
      return nextForm;
    });
    window.setTimeout(async () => {
      setAutoPlanning(true);
      try {
        await generatePlan(nextForm, true);
      } catch (e) {
        toast("Plan did not update.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
      } finally {
        setAutoPlanning(false);
      }
    }, 0);
  };
  const proteinChoices = form.protein_weeks || (form.protein_week ? [form.protein_week] : []);
  const generatePlan = async (nextForm = form, quiet = false) => {
    const selected = nextForm.protein_weeks || (nextForm.protein_week ? [nextForm.protein_week] : []);
    if (!selected.length) {
      if (!quiet) toast("Pick at least one protein. The fridge needs a plot.");
      return null;
    }
    const res = await saveFoodV1({ ...nextForm, protein_weeks: selected, protein_week: selected[0] });
    setData((prev) => ({ ...prev, plan: res.plan, week_start: res.plan.week_start }));
    setForm(res.plan.inputs);
    return res;
  };
  const toggleProtein = (protein) => {
    let nextForm = null;
    setForm((prev) => {
      const current = prev.protein_weeks || (prev.protein_week ? [prev.protein_week] : []);
      const exists = current.includes(protein);
      const next = exists ? current.filter((item) => item !== protein) : [...current, protein].slice(0, 5);
      nextForm = { ...prev, protein_weeks: next, protein_week: next[0] || "" };
      return nextForm;
    });
    window.setTimeout(async () => {
      if (!nextForm?.protein_weeks?.length) return;
      setAutoPlanning(true);
      try {
        await generatePlan(nextForm, true);
      } catch (e) {
        toast("Plan did not update.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
      } finally {
        setAutoPlanning(false);
      }
    }, 0);
  };

  const save = async () => {
    setBusy(true);
    try {
      await generatePlan({ ...form, protein_weeks: proteinChoices, protein_week: proteinChoices[0] });
      toast("Week handled. Civilization may continue.");
    } catch (e) {
      toast("Food plan did not save.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const plan = data?.plan;
  const planDays = useMemo(() => plan?.days || [], [plan]);
  const lunchOptions = data?.lunch_options?.length ? data.lunch_options : FALLBACK_LUNCH_OPTIONS;
  const proteinOptions = data?.protein_options?.length ? data.protein_options : FALLBACK_PROTEIN_OPTIONS;
  const budgetFeelings = data?.budget_feelings?.length ? data.budget_feelings : FALLBACK_BUDGET_FEELINGS;

  return (
    <section className="space-y-6" data-testid="food-v1">
      <div>
        <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em] mb-2">
          <Utensils size={14} /> Saturday to Saturday
        </div>
        <h2 className="font-heading text-3xl text-moss-50">What are we eating?</h2>
        <p className="text-sm text-moss-200 mt-2 max-w-2xl">
          Pick 2-5 proteins and the planner builds muscle-friendly meals, snacks, and a shopping list. No tuna. No beans. Civilization survives.
        </p>
      </div>

      <div className="warm-card rounded-3xl p-5">
        <div className="grid md:grid-cols-3 gap-3">
          <input data-testid="food-week-start" type="date" value={form.week_start || ""} onChange={(e) => setField("week_start", e.target.value)} className={inputCls} />
          <label className="space-y-1">
            <span className="text-xs uppercase tracking-[0.2em] text-moss-200/75">Preferred lunch format</span>
            <select data-testid="food-lunch" value={form.lunch_week || ""} onChange={(e) => setFieldAndRegenerate("lunch_week", e.target.value)} className={inputCls}>
              {lunchOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <span className="block text-xs text-moss-200/70">Pick the structure. The planner varies the fillings.</span>
          </label>
          <select data-testid="food-budget-feeling" value={form.budget_feeling || "normal"} onChange={(e) => setField("budget_feeling", e.target.value)} className={inputCls}>
            {budgetFeelings.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <input data-testid="food-breakfast" value={form.breakfast_default || ""} onChange={(e) => setField("breakfast_default", e.target.value)} placeholder="breakfast default" className={inputCls + " md:col-span-3"} />
        </div>
        <div className="mt-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70">weekly proteins, pick 2-5</div>
            {autoPlanning && <div className="text-xs text-amber">updating meals...</div>}
          </div>
          <div className="flex flex-wrap gap-2">
            {proteinOptions.map((item) => {
              const active = proteinChoices.includes(item);
              return (
                <button
                  key={item}
                  type="button"
                  data-testid={`food-protein-${item}`}
                  onClick={() => toggleProtein(item)}
                  className={`rounded-full border px-3 py-2 text-xs transition-colors ${active ? "border-amber bg-amber/15 text-amber" : "border-moss-700 bg-moss-800/50 text-moss-100 hover:border-moss-500"}`}
                >
                  {item}
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid md:grid-cols-3 gap-3 mt-3">
          <textarea data-testid="food-shifts" value={form.shifts || ""} onChange={(e) => setField("shifts", e.target.value)} placeholder="shifts" className={inputCls + " min-h-[76px] resize-none"} />
          <textarea data-testid="food-training" value={form.training_schedule || ""} onChange={(e) => setField("training_schedule", e.target.value)} placeholder="training" className={inputCls + " min-h-[76px] resize-none"} />
          <textarea data-testid="food-leftovers" value={form.leftovers || ""} onChange={(e) => setField("leftovers", e.target.value)} placeholder="leftovers already home" className={inputCls + " min-h-[76px] resize-none"} />
        </div>
        <button data-testid="food-save" disabled={busy || autoPlanning} onClick={save} className="pill-btn primary rounded-full px-5 py-2 text-xs inline-flex items-center gap-2 mt-4">
          <CalendarDays size={13} /> Regenerate week
        </button>
      </div>

      {plan && (
        <div className="grid lg:grid-cols-[1.4fr_0.8fr] gap-5">
          <div className="warm-card rounded-3xl p-5">
            <h3 className="font-heading text-xl text-moss-50 mb-4">Week plan</h3>
            <div className="space-y-3">
              {planDays.map((day) => (
                <div key={day.date} className="grid md:grid-cols-[100px_1fr] gap-3 border-b border-moss-700/60 pb-3 last:border-b-0">
                  <div>
                    <div className="text-amber font-heading text-sm">{day.day}</div>
                    <div className="text-moss-200 text-xs">{day.date.slice(5)}</div>
                  </div>
                  <div className="text-sm text-moss-100 leading-relaxed">
                    <div><span className="text-moss-200">Breakfast:</span> {day.breakfast}</div>
                    <div><span className="text-moss-200">Lunch:</span> {day.lunch}</div>
                    <div><span className="text-moss-200">Dinner:</span> {day.dinner}</div>
                    <div><span className="text-moss-200">Snack:</span> {day.snack}</div>
                    <div><span className="text-moss-200">Protein target:</span> {day.protein_estimate_g || 125}g-ish</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="warm-card rounded-3xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingBasket size={15} className="text-amber" />
              <h3 className="font-heading text-xl text-moss-50">Shopping list</h3>
            </div>
            <ul className="space-y-2 text-sm text-moss-100">
              {(plan.shopping_list || []).map((item) => <li key={item}>- {item}</li>)}
            </ul>
            <div className="mt-5 text-xs uppercase tracking-[0.22em] text-moss-200/70">protein logic</div>
            <div className="text-sm text-moss-100 mt-2">
              Target: <span className="text-amber">{plan.protein_target || "120-140g/day"}</span>. Main meals aim for <span className="text-amber">{plan.main_meal_protein_target || "25-40g"}</span>.
            </div>
            {(plan.lunch_variations || []).length > 0 && (
              <div className="mt-4">
                <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-2">lunch format: {plan.lunch_style || form.lunch_week}</div>
                <ul className="space-y-1 text-sm text-moss-100">
                  {plan.lunch_variations.map((item) => <li key={item}>- {item}</li>)}
                </ul>
              </div>
            )}
            {(plan.snack_suggestions || []).length > 0 && (
              <div className="mt-4">
                <div className="text-xs uppercase tracking-[0.22em] text-moss-200/70 mb-2">snacks</div>
                <ul className="space-y-1 text-sm text-moss-100">
                  {plan.snack_suggestions.map((item) => <li key={item}>- {item}</li>)}
                </ul>
              </div>
            )}
            <div className="mt-5 text-xs uppercase tracking-[0.22em] text-moss-200/70">rough estimate</div>
            <div className="font-heading text-2xl text-moss-50">{plan.grocery_estimate} kr</div>
            <p className="text-sm text-moss-200 italic mt-4">{plan.note}</p>
          </div>
        </div>
      )}
    </section>
  );
}

export default function BudgetFoodPage() {
  return (
    <div className="px-5 md:px-12 py-7 md:py-16 max-w-6xl mx-auto" data-testid="budget-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Household ledger</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Budget Room</h1>
        <p className="text-moss-200 mt-3 font-body italic max-w-xl">
          Money records without moral theatre. Useful numbers, fewer mystery leaks.
        </p>
      </div>
      <BudgetV1 />
    </div>
  );
}
