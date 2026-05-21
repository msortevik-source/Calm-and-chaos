import { useEffect, useState } from "react";
import { CalendarDays, Link as LinkIcon, RefreshCw } from "lucide-react";
import { calendarStatus, calendarToday, calendarLoginUrl } from "../lib/api";

function fmtTime(iso, all_day) {
  if (!iso) return "";
  if (all_day) return "all day";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } catch { return ""; }
}

export default function CalendarSnapshot() {
  const [linked, setLinked] = useState(false);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const s = await calendarStatus();
      setLinked(s.linked);
      if (s.linked) {
        const d = await calendarToday();
        setEvents(d.events || []);
      }
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const connect = async () => {
    const { authorization_url } = await calendarLoginUrl();
    window.location.href = authorization_url;
  };

  return (
    <div className="rounded-3xl border border-moss-700 bg-moss-800/60 p-6" data-testid="calendar-snapshot">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-moss-200 text-xs uppercase tracking-[0.25em]">
          <CalendarDays size={14} />
          What's today
        </div>
        {linked && (
          <button data-testid="calendar-refresh" onClick={load} className="text-moss-200 hover:text-amber transition-colors">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        )}
      </div>

      {!linked && (
        <div className="space-y-3">
          <p className="text-moss-200 font-body text-sm leading-relaxed">
            Link Google Calendar to see what's actually on the docket. Optional. The room works without it.
          </p>
          <button data-testid="calendar-connect" onClick={connect} className="pill-btn rounded-full px-4 py-1.5 text-xs inline-flex items-center gap-2">
            <LinkIcon size={13} /> Link calendar
          </button>
        </div>
      )}

      {linked && events.length === 0 && !loading && (
        <p className="text-moss-200 font-body text-sm italic" data-testid="calendar-empty">
          Nothing on the calendar. A quiet afternoon, apparently.
        </p>
      )}

      {linked && events.length > 0 && (
        <ul className="space-y-3" data-testid="calendar-events">
          {events.slice(0, 6).map(ev => (
            <li key={ev.id} className="flex items-start gap-3 group">
              <div className="text-amber font-heading text-sm w-16 shrink-0 pt-0.5">
                {fmtTime(ev.start, ev.all_day)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-moss-50 text-sm leading-snug truncate">{ev.summary}</div>
                {ev.location && <div className="text-moss-200 text-xs truncate">{ev.location}</div>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
