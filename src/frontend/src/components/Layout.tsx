import type { PropsWithChildren } from "react"
import { NavLink } from "react-router-dom"

const NAV_ITEMS = [{ to: "/", label: "Trial Overview", icon: IconGrid }]

export function Layout({ children }: PropsWithChildren) {
  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink lg:flex-row">
      <aside className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-5 py-4 lg:w-60 lg:flex-col lg:items-stretch lg:gap-6 lg:border-b-0 lg:border-r lg:py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
            C
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink">ClinIQ</div>
            <div className="text-[11px] text-muted">Risk Monitor</div>
          </div>
        </div>

        <nav className="hidden flex-1 flex-col gap-1 lg:flex">
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

        <div className="mt-auto hidden text-[11px] text-muted lg:block">
          TRIAL-2026-ONC-04
          <br />
          Phase III Oncology
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
