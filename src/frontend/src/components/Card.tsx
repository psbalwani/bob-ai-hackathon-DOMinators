import type { PropsWithChildren } from "react"

export function Card({
  children,
  className = "",
  hoverable = false,
}: PropsWithChildren<{ className?: string; hoverable?: boolean }>) {
  return (
    <div
      className={`rounded-card border border-border bg-card shadow-card transition-shadow duration-200 ${
        hoverable ? "hover:shadow-card-hover" : ""
      } ${className}`}
    >
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
