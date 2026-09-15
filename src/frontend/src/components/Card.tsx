import type { PropsWithChildren } from "react"

export function Card({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return (
    <div className={`rounded-card border border-border bg-card shadow-sm ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return <div className={`border-b border-border px-5 py-4 ${className}`}>{children}</div>
}

export function CardBody({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return <div className={`p-5 ${className}`}>{children}</div>
}
