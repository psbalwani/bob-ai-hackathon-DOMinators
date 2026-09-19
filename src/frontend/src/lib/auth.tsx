import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react"
import { api, setAuthToken } from "./api"
import type { AuthUser } from "./api"

interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  currentProtocolId: string | null
  setCurrentProtocolId: (protocolId: string) => void
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

const TOKEN_KEY = "cliniq.token"
const PROTOCOL_KEY = "cliniq.currentProtocolId"

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [currentProtocolId, setCurrentProtocolIdState] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Restore a session from localStorage on first load, so a page refresh
  // doesn't bounce a logged-in drug owner back to the login screen.
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setIsLoading(false)
      return
    }
    setAuthToken(token)
    api
      .getMe()
      .then((me) => {
        setUser(me)
        setCurrentProtocolIdState(pickInitialProtocol(me))
      })
      .catch(() => {
        // Token expired or invalid -- drop it and fall through to login.
        localStorage.removeItem(TOKEN_KEY)
        setAuthToken(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  function pickInitialProtocol(me: AuthUser): string | null {
    const saved = localStorage.getItem(PROTOCOL_KEY)
    if (saved && me.protocols.some((p) => p.protocol_id === saved)) return saved
    return me.protocols[0]?.protocol_id ?? null
  }

  async function login(username: string, password: string) {
    const res = await api.login(username, password)
    localStorage.setItem(TOKEN_KEY, res.access_token)
    setAuthToken(res.access_token)
    setUser(res.user)
    const initial = pickInitialProtocol(res.user)
    setCurrentProtocolIdState(initial)
    if (initial) localStorage.setItem(PROTOCOL_KEY, initial)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(PROTOCOL_KEY)
    setAuthToken(null)
    setUser(null)
    setCurrentProtocolIdState(null)
  }

  function setCurrentProtocolId(protocolId: string) {
    setCurrentProtocolIdState(protocolId)
    localStorage.setItem(PROTOCOL_KEY, protocolId)
  }

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      currentProtocolId,
      setCurrentProtocolId,
      login,
      logout,
    }),
    [user, isLoading, currentProtocolId],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider")
  return ctx
}
