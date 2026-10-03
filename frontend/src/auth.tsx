import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, api, getToken, setToken, setUnauthorizedHandler } from './api/client'
import type { User } from './api/types'
import { useI18n } from './i18n'

interface Auth {
  user: User | null
  ready: boolean                       // false while the saved session is checked
  unreachable: boolean                 // the server could not be reached (token kept)
  retry: () => void
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  updateProfile: (patch: Partial<Pick<User, 'name' | 'min_coverage' | 'language'>>) => Promise<void>
}

const Ctx = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(() => !getToken())
  const [unreachable, setUnreachable] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => { setUnreachable(false); setReady(false); setAttempt((a) => a + 1) }, [])
  const { setLang } = useI18n()

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const signedIn = useCallback((u: User) => {
    setUser(u)
    setLang(u.language)                // the profile's language wins once logged in
  }, [setLang])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!getToken()) return
    api.me()
      .then(signedIn)
      .catch((e) => {
        // only a rejected token logs out; a server or network hiccup keeps the session
        if (e instanceof ApiError && e.status === 401) setToken(null)
        else setUnreachable(true)
      })
      .finally(() => setReady(true))
  }, [logout, signedIn, attempt])

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.login(email, password)
    setToken(r.token)
    signedIn(r.user)
  }, [signedIn])

  const register = useCallback(async (email: string, password: string, name: string) => {
    const r = await api.register(email, password, name)
    setToken(r.token)
    // a new account starts in the language chosen before signing up
    const lang = document.documentElement.lang as User['language']
    signedIn(lang && lang !== r.user.language ? await api.updateMe({ language: lang }) : r.user)
  }, [signedIn])

  const updateProfile = useCallback(async (patch: Partial<Pick<User, 'name' | 'min_coverage' | 'language'>>) => {
    signedIn(await api.updateMe(patch))
  }, [signedIn])

  const value = useMemo(() => ({ user, ready, unreachable, retry, login, register, logout, updateProfile }),
    [user, ready, unreachable, retry, login, register, logout, updateProfile])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): Auth {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth outside AuthProvider')
  return v
}
