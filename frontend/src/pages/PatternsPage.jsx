import { useEffect, useState } from "react";
import { getPatterns } from "../lib/api";
import { Sparkles } from "lucide-react";

export default function PatternsPage() {
  const [obs, setObs] = useState([]);

  useEffect(() => {
    getPatterns().then(d => setObs(d.observations || [])).catch(() => {});
  }, []);

  return (
    <div className="px-6 md:px-12 py-10 md:py-16 max-w-3xl mx-auto" data-testid="patterns-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.25em] text-moss-200/70 mb-2">Weather is not climate</div>
        <h1 className="font-heading text-4xl md:text-5xl text-moss-50">Patterns</h1>
        <p className="text-moss-200 mt-3 font-body italic max-w-xl">
          One bad day is noted. Repeated evidence is surfaced gently. Nothing here is a verdict.
        </p>
      </div>

      <div className="space-y-5" data-testid="observations">
        {obs.map((o, i) => (
          <div key={i} className="rounded-3xl border border-moss-700 bg-moss-800/50 p-6 animate-fade-up" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-amber/80 mb-3">
              <Sparkles size={12} /> {o.kind}
            </div>
            <h3 className="font-heading text-xl md:text-2xl text-moss-50 leading-snug">{o.title}</h3>
            <p className="text-moss-200 mt-2 font-body leading-relaxed">{o.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
