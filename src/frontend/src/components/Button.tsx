import type { ButtonHTMLAttributes, PropsWithChildren } from "react"

type Variant = "primary" | "secondary" | "ghost" | "success" | "danger"

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand-strong disabled:hover:bg-brand",
  secondary: "border border-border bg-card text-ink hover:bg-surface",
  ghost: "text-muted hover:bg-surface hover:text-ink",
  success: "bg-risk-low text-white hover:opacity-90 disabled:hover:opacity-100",
  danger: "border border-border text-ink hover:bg-surface",
}

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: Variant
    size?: "sm" | "md"
  }
>

export function Button({ children, variant = "secondary", size = "md", className = "", ...rest }: ButtonProps) {
  const sizeClasses = size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-sm"
  return (
    <button
      className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${sizeClasses} ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
