import type { PropsWithChildren } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../lib/auth"
import { useTheme } from "../lib/theme"
import { IconMoon, IconShieldCheck, IconSun } from "./icons"

const NAV_ITEMS = [
  { to: "/", label: "Trial Overview", icon: IconGrid },
  { to: "/drug-performance", label: "Drug Performance", icon: IconShieldCheck },
]

export function Layout({ children }: PropsWithChildren) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, currentProtocolId, setCurrentProtocolId, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const currentProtocol = user?.protocols.find((p) => p.protocol_id === currentProtocolId)

  function handleLogout() {
    logout()
    navigate("/login", { replace: true })
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
      <aside className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-5 py-4 lg:w-64 lg:flex-col lg:items-stretch lg:gap-7 lg:border-b-0 lg:border-r lg:py-6">
        <div className="flex flex-1 items-center justify-between gap-2.5 lg:flex-initial">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-brand-strong text-base font-bold text-white shadow-card">
              C
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-ink">ClinIQ</div>
              <div className="text-[11px] text-muted">Trial Risk Monitor</div>
            </div>
          </div>

          <button
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-ink"
          >
            {theme === "dark" ? <IconSun className="h-4 w-4" /> : <IconMoon className="h-4 w-4" />}
          </button>
        </div>

        <nav className="hidden flex-1 flex-col gap-1 lg:flex">
          <div className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted">Monitor</div>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface hover:text-ink"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto hidden flex-col gap-2 lg:flex">
          {user && user.protocols.length > 0 && (
            <div className="rounded-lg border border-border bg-surface px-3 py-2.5">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                {user.protocols.length > 1 ? "Switch drug" : "Drug"}
              </div>
              {user.protocols.length > 1 ? (
                <select
                  value={currentProtocolId ?? ""}
                  onChange={(e) => {
                    setCurrentProtocolId(e.target.value)
                    navigate("/")
                  }}
                  className="w-full bg-transparent text-[11px] font-medium text-ink focus:outline-none"
                >
                  {user.protocols.map((p) => (
                    <option key={p.protocol_id} value={p.protocol_id}>
                      {p.drug} · {p.protocol_id}
                    </option>
                  ))}
                </select>
              ) : (
                <>
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-ink">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-risk-low opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-risk-low" />
                    </span>
                    {currentProtocol?.protocol_id}
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted">{currentProtocol?.drug}</div>
                </>
              )}
            </div>
          )}
          <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-3 py-2 text-[11px]">
            <span className="font-medium text-ink">{user?.username}</span>
            <button onClick={handleLogout} className="font-medium text-muted transition-colors hover:text-ink">
              Log out
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-x-hidden">
        <div key={location.pathname} className="animate-page-in">
          {children}
        </div>
      </main>
    </div>
  )
}

function IconGrid({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden>
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}
