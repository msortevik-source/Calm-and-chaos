import { NavLink, Outlet } from "react-router-dom";
import { Home, BarChart3, Activity, Sparkles, Wallet, Mail, ClipboardList } from "lucide-react";
import Goblin from "./Goblin";

const links = [
  { to: "/", label: "Hearth", icon: Home, testid: "nav-home", mobile: true },
  { to: "/conversation", label: "Spirit", icon: BarChart3, testid: "nav-conversation", mobile: true },
  { to: "/training", label: "Trails", icon: Activity, testid: "nav-training", mobile: true },
  { to: "/budget", label: "Ledger", icon: Wallet, testid: "nav-budget", mobile: true },
  { to: "/life-upgrades", label: "Board", icon: ClipboardList, testid: "nav-life-upgrades", mobile: true },
  { to: "/letter", label: "Letters", icon: Mail, testid: "nav-letter" },
  { to: "/patterns", label: "Weather", icon: Sparkles, testid: "nav-patterns" },
];

function seasonLabel() {
  const month = new Date().getMonth();
  if (month <= 1 || month === 11) return "winter station";
  if (month >= 2 && month <= 4) return "spring station";
  if (month >= 5 && month <= 7) return "summer station";
  return "autumn station";
}

export default function Shell() {
  const season = seasonLabel();
  return (
    <div className="app-root warm-depth grain-overlay">
      <div className="content-layer min-h-screen flex">
        <aside className="hidden md:flex flex-col w-72 px-7 py-8 border-r sticky top-0 h-screen wood-rail" data-testid="sidebar">
          <div className="mb-12">
            <div className="inline-block rounded-sm border border-amber/40 bg-[#2f231b]/75 px-4 py-3 shadow-sm">
              <div className="font-heading text-2xl text-moss-50 leading-tight">Calm <span className="text-amber">&</span> Chaos</div>
              <div className="text-[10px] text-moss-200 mt-1 tracking-[0.18em] uppercase">{season}</div>
            </div>
          </div>
          <nav className="flex flex-col gap-5">
            {links.map(l => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                data-testid={l.testid}
                className={({ isActive }) =>
                  `nav-link flex items-center gap-3 text-sm tracking-wide ${isActive ? "active text-moss-50" : "text-moss-200"}`
                }
              >
                <l.icon size={16} className="opacity-80" />
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto pt-8">
            <div className="house-spirit-note rounded-md p-3 text-xs leading-relaxed">
              <div className="flex items-center gap-3">
                <Goblin size={54} />
                <div>
                  <p className="font-heading text-base text-moss-50 leading-tight">House spirit note</p>
                  <p className="text-moss-100/90 italic mt-1">Records reviewed. Nothing is on fire unless proven otherwise.</p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <header className="md:hidden fixed top-0 left-0 right-0 z-30 wood-rail border-b">
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <div className="font-heading text-lg text-moss-50">Calm <span className="text-amber">&</span> Chaos</div>
              <div className="text-[9px] uppercase tracking-[0.18em] text-moss-200/80">{season}</div>
            </div>
          </div>
        </header>

        <main className="flex-1 pt-24 pb-28 md:pt-0 md:pb-0">
          <Outlet />
        </main>

        <nav className="bottom-room-nav md:hidden" aria-label="Primary rooms">
          {links.filter((l) => l.mobile).map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              data-testid={`m-${l.testid}`}
              className={({ isActive }) => `bottom-room-link ${isActive ? "active" : ""}`}
            >
              <l.icon size={19} />
              <span>{l.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
