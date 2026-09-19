import { useCallback, useEffect, useState } from "react"

export type Theme = "light" | "dark"

const STORAGE_KEY = "cliniq.theme"

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches
}

function readStoredTheme(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === "light" || v === "dark" ? v : null
  } catch {
    // Private browsing / blocked storage -- fall back to system preference.
    return null
  }
}

/** Theme toggle state, backed by `<html data-theme="...">` (see index.css)
 * and persisted to localStorage. Seeds from system preference on first
 * load so a user who never touches the toggle still gets the right look;
 * once they do, the explicit choice sticks across reloads and no longer
 * follows a later system preference change (standard toggle behavior). */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => readStoredTheme() ?? (systemPrefersDark() ? "dark" : "light"))

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Ignore -- theme still applies for this session, just won't persist.
    }
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark")
  }, [theme, setTheme])

  return { theme, toggleTheme }
}
