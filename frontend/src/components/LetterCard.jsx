import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Link } from "react-router-dom";
import { Mail } from "lucide-react";

export default function LetterCard() {
  const [letter, setLetter] = useState(null);

  useEffect(() => {
    api.get("/letter/archive?limit=1").then(r => {
      const l = (r.data.letters || [])[0];
      if (l) setLetter(l);
    }).catch(() => {});
  }, []);

  if (!letter) return null;

  const preview = (letter.body || "").replace(/\*\*/g, "").split("\n").filter(Boolean).slice(0, 2).join(" ");

  return (
    <Link to="/letter" className="block" data-testid="home-letter-card">
      <div className="rounded-3xl warm-card p-6 hover:border-amber/40 transition-colors" style={{ background: "linear-gradient(180deg, rgba(212,163,115,0.08) 0%, rgba(43,47,42,0.85) 100%)" }}>
        <div className="flex items-center gap-2 text-amber/90 text-xs uppercase tracking-[0.25em] mb-3">
          <Mail size={14} /> Letter from the room · {letter.week_key}
        </div>
        <p className="text-moss-50 font-heading italic text-base md:text-lg leading-snug line-clamp-3">
          {preview.slice(0, 220)}{preview.length > 220 ? "…" : ""}
        </p>
        <div className="mt-3 text-xs text-amber/80">read it →</div>
      </div>
    </Link>
  );
}
