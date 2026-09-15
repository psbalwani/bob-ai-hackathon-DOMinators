import type { PropsWithChildren } from "react"
import { NavLink } from "react-router-dom"

const NAV_ITEMS = [{ to: "/", label: "Trial Overview", icon: IconGrid }]

export function Layout({ children }: PropsWithChildren) {
  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
      <aside className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-5 py-4 lg:w-64 lg:flex-col lg:items-stretch lg:gap-7 lg:border-b-0 lg:border-r lg:py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-brand-strong text-base font-bold text-white shadow-card">
            C
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink">ClinIQ</div>
            <div className="text-[11px] text-muted">Trial Risk Monitor</div>
          </div>
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

        <div className="mt-auto hidden rounded-lg border border-border bg-surface px-3 py-2.5 lg:block">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-ink">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-risk-low opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-risk-low" />
            </span>
            TRIAL-2026-ONC-04
          </div>
          <div className="mt-0.5 text-[11px] text-muted">Phase III Oncology</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
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
