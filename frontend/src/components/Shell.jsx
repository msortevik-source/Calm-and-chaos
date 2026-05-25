import { NavLink, Outlet } from "react-router-dom";
import { Home, BarChart3, Activity, Sparkles, Wallet, Mail, ClipboardList } from "lucide-react";

const links = [
  { to: "/", label: "Home", icon: Home, testid: "nav-home" },
  { to: "/conversation", label: "Analysis Corner", icon: BarChart3, testid: "nav-conversation" },
  { to: "/training", label: "Training", icon: Activity, testid: "nav-training" },
  { to: "/budget", label: "Budget & food", icon: Wallet, testid: "nav-budget" },
  { to: "/life-upgrades", label: "Life Upgrades", icon: ClipboardList, testid: "nav-life-upgrades" },
  { to: "/letter", label: "Letter", icon: Mail, testid: "nav-letter" },
  { to: "/patterns", label: "Patterns", icon: Sparkles, testid: "nav-patterns" },
];

export default function Shell() {
  return (
    <div className="app-root warm-depth grain-overlay">
      <div className="content-layer min-h-screen flex">
        <aside className="hidden md:flex flex-col w-64 px-8 py-10 border-r border-moss-700/70 sticky top-0 h-screen" data-testid="sidebar">
          <div className="mb-12">
            <div className="font-heading text-2xl text-moss-50 leading-tight">Calm <span className="text-amber">&</span> Chaos</div>
            <div className="text-xs text-moss-200 mt-1 tracking-wide">observant analyst with receipts</div>
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
          <div className="mt-auto pt-8 text-xs text-moss-200/80 leading-relaxed">
            <p className="italic">Patterns over motivation.</p>
            <p className="italic">Receipts over shame.</p>
          </div>
        </aside>

        <header className="md:hidden fixed top-0 left-0 right-0 z-30 bg-moss-900 border-b border-moss-700/70">
          <div className="flex items-center justify-between px-5 py-4">
            <div className="font-heading text-lg text-moss-50">Calm <span className="text-amber">&</span> Chaos</div>
          </div>
          <nav className="flex overflow-x-auto px-3 pb-3 gap-4 text-xs">
            {links.map(l => (
              <NavLink key={l.to} to={l.to} end={l.to === "/"} data-testid={`m-${l.testid}`}
                className={({ isActive }) => `whitespace-nowrap px-2 py-1 rounded-full ${isActive ? "text-amber bg-amber/10" : "text-moss-200"}`}>
                {l.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="flex-1 pt-32 md:pt-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
