import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ClipboardList, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  createLifeUpgrade,
  deleteLifeUpgrade,
  listLifeUpgrades,
  updateLifeUpgrade,
} from "../lib/api";

const inputCls = "bg-moss-800/60 border border-moss-700 rounded-xl px-3 py-2 text-sm text-moss-50 placeholder-moss-200/50 outline-none focus:border-amber/50 transition-colors";
const emptyForm = { title: "", category: "Home", note: "", estimated_cost: "", priority: "" };
const defaultCategories = ["Home", "Maintenance", "Purchases", "Outdoor", "Storage", "Someday"];
const defaultPriorities = ["low", "medium", "high"];

const money = (value) => {
  if (value === undefined || value === null || value === "") return null;
  const amount = Number(value);
  if (Number.isNaN(amount)) return null;
  return `${new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 0 }).format(amount)} kr`;
};

function ItemCard({ item, onToggle, onDelete }) {
  const cost = money(item.estimated_cost);

  return (
    <div className={`warm-card rounded-2xl p-4 ${item.completed ? "opacity-80" : ""}`} data-testid="life-upgrade-item">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => onToggle(item)}
          className={`mt-0.5 h-6 w-6 rounded-full border flex items-center justify-center transition-colors ${
            item.completed ? "bg-amber text-moss-950 border-amber" : "border-moss-600 text-moss-200 hover:border-amber"
          }`}
          aria-label={item.completed ? "Mark active" : "Mark complete"}
        >
          {item.completed && <Check size={14} />}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className={`font-heading text-xl leading-tight ${item.completed ? "text-moss-200 line-through" : "text-moss-50"}`}>
              {item.title}
            </h3>
            <span className="text-[10px] uppercase tracking-[0.18em] text-amber/90 bg-amber/10 rounded-full px-2 py-1">
              {item.category}
            </span>
            {item.priority && (
              <span className="text-[10px] uppercase tracking-[0.18em] text-moss-200/80 border border-moss-700 rounded-full px-2 py-1">
                {item.priority}
              </span>
            )}
          </div>

          {item.note && <p className="text-sm text-moss-200 mt-2 leading-relaxed">{item.note}</p>}

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-moss-200/70 mt-3">
            <span>Added {item.created_date}</span>
            {cost && <span>Estimate {cost}</span>}
            {item.completed_date && <span>Done {item.completed_date}</span>}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onDelete(item)}
          className="text-moss-200/60 hover:text-amber transition-colors p-1"
          aria-label="Delete item"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
}

export default function LifeUpgradesPage() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState(defaultCategories);
  const [priorities, setPriorities] = useState(defaultPriorities);
  const [form, setForm] = useState(emptyForm);
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState("active");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const res = await listLifeUpgrades();
    setItems(res.items || []);
    setCategories(res.categories || defaultCategories);
    setPriorities(res.priorities || defaultPriorities);
  }, []);

  useEffect(() => {
    load().catch(() => toast("Life Upgrades refused to load. Suspicious."));
  }, [load]);

  const visibleItems = useMemo(() => {
    return items.filter((item) => {
      const matchesView = view === "done" ? item.completed : !item.completed;
      const matchesCategory = filter === "all" || item.category === filter;
      return matchesView && matchesCategory;
    });
  }, [items, filter, view]);

  const activeCount = items.filter((item) => !item.completed).length;
  const doneCount = items.filter((item) => item.completed).length;

  const addItem = async (event) => {
    event.preventDefault();
    const title = form.title.trim();
    if (!title) {
      toast("Give the mental tab a name first.");
      return;
    }

    setBusy(true);
    try {
      await createLifeUpgrade({
        ...form,
        title,
        estimated_cost: form.estimated_cost ? Number(form.estimated_cost) : null,
        priority: form.priority || null,
        note: form.note || null,
      });
      setForm({ ...emptyForm, category: form.category });
      await load();
      toast("Parked. You no longer have to keep remembering it.");
    } catch (e) {
      toast("Life upgrade did not save.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const toggleItem = async (item) => {
    setBusy(true);
    try {
      await updateLifeUpgrade(item.id, { completed: !item.completed });
      await load();
    } catch (e) {
      toast("Life upgrade did not update.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  const removeItem = async (item) => {
    setBusy(true);
    try {
      await deleteLifeUpgrade(item.id);
      await load();
    } catch (e) {
      toast("Life upgrade did not delete.", { description: e?.response?.data?.detail || e?.message || "No useful error returned." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-5 md:px-12 py-7 md:py-16 max-w-5xl mx-auto" data-testid="life-upgrades-page">
      <div className="mb-8">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Notice board</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Future Projects</h1>
        <p className="text-moss-200 mt-3 font-body italic max-w-xl">
          Pinned ideas, possible projects, wishlist items. No alarms. No guilt.
        </p>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] gap-5 items-start">
        <form onSubmit={addItem} className="warm-card rounded-3xl p-5 space-y-4" data-testid="life-upgrade-form">
          <div className="flex items-center gap-2">
            <Plus size={16} className="text-amber" />
            <h2 className="font-heading text-2xl text-moss-50">Pin something</h2>
          </div>

          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-moss-200/70">title</span>
            <input
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="buy proper pant basket"
              className={`${inputCls} mt-1 w-full`}
              data-testid="life-title"
            />
          </label>

          <div className="grid sm:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs uppercase tracking-[0.18em] text-moss-200/70">category</span>
              <select
                value={form.category}
                onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
                className={`${inputCls} mt-1 w-full`}
              >
                {categories.map((cat) => <option key={cat}>{cat}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-[0.18em] text-moss-200/70">priority</span>
              <select
                value={form.priority}
                onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value }))}
                className={`${inputCls} mt-1 w-full`}
              >
                <option value="">Not dramatic</option>
                {priorities.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-moss-200/70">estimated cost</span>
            <input
              type="number"
              min="0"
              value={form.estimated_cost}
              onChange={(e) => setForm((prev) => ({ ...prev, estimated_cost: e.target.value }))}
              placeholder="NOK"
              className={`${inputCls} mt-1 w-full`}
            />
          </label>

          <label className="block">
            <span className="text-xs uppercase tracking-[0.18em] text-moss-200/70">note</span>
            <textarea
              value={form.note}
              onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))}
              placeholder="optional context, measurements, link, whatever"
              className={`${inputCls} mt-1 w-full min-h-[88px] resize-none`}
            />
          </label>

          <button disabled={busy} className="pill-btn primary rounded-full px-5 py-2 text-xs w-full sm:w-auto" data-testid="life-add">
            Pin to board
          </button>
        </form>

        <section className="space-y-4">
          <div className="warm-card rounded-3xl p-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ClipboardList size={16} className="text-amber" />
                <div>
                  <div className="font-heading text-2xl text-moss-50">Notice Board</div>
                  <div className="text-xs text-moss-200/70">{activeCount} active | {doneCount} done</div>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <div className="flex rounded-full border border-moss-700 p-1 bg-moss-900/40">
                  {["active", "done"].map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setView(mode)}
                      className={`rounded-full px-3 py-1 text-xs capitalize transition-colors ${view === mode ? "bg-amber text-moss-950" : "text-moss-200"}`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2">
                  <SlidersHorizontal size={14} className="text-moss-200/70" />
                  <select value={filter} onChange={(e) => setFilter(e.target.value)} className={inputCls}>
                    <option value="all">All categories</option>
                    {categories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div className="space-y-3" data-testid="life-upgrade-list">
            {visibleItems.length === 0 ? (
              <div className="warm-card rounded-2xl p-6 text-moss-200">
                {view === "done" ? "Nothing completed here yet. Quietly rude, but fine." : "No active items in this filter. Suspiciously peaceful."}
              </div>
            ) : (
              visibleItems.map((item) => (
                <ItemCard key={item.id} item={item} onToggle={toggleItem} onDelete={removeItem} />
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
