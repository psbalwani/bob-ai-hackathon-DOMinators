# ClinIQ Dashboard (Track D)

React + Vite + Tailwind frontend for the risk-monitoring dashboard. Talks to the Track D
gateway (`src/backend`) on `http://localhost:8000` by default — see `.env.example` to
point it elsewhere, and `docs/setup-guide.md` for the full run instructions.

## Run

```bash
npm install
npm run dev
```

Opens at `http://localhost:5173`.

## Pages

| Route | Screen |
|---|---|
| `/` | Trial Overview — ranked sites, filters, search |
| `/sites/:siteId` | Site Drill-down — risk score, indicator breakdown chart, deviation list, CAPA reports |
| `/deviations/:deviationId` | Deviation Detail — severity rationale, protocol clause citation, visit record |
| `/capa/:capaId` | CAPA Report — root cause / corrective / preventive action, evidence citations, Markdown export |

## Design system

Design tokens (colors, radii, fonts) live in `src/index.css` under Tailwind v4's
`@theme` block — risk-band colors (`risk-high`/`risk-medium`/`risk-low`) are kept
visually distinct from the brand color so severity is never ambiguous. Both light and
dark mode are supported via `prefers-color-scheme`.

The site table on Trial Overview switches to a stacked card layout below the `sm`
breakpoint instead of a horizontally-scrolling table, so every column (risk score,
band, trend, open deviations) stays visible without a hidden scroll on mobile.
