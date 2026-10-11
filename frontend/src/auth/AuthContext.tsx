import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, type ReactNode } from 'react'
import { api, ApiError } from '../api/client'

export type Me = { id: string; email: string; role: string; is_demo: boolean; impersonated_by: string | null }
type Ctx = {
  me: Me | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}
const AuthCtx = createContext<Ctx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try { return await api<Me>('/auth/me') } catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e }
    },
  })
  // Сменился пользователь (вход, выход, демо-персона): данные прошлого пользователя в кэше не годятся.
  // Ждём только «я»; остальное сбрасывается сразу и перезапрашивается в фоне — без ожидания запросов, которые новому пользователю запрещены
  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ['me'] })
    void qc.resetQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
  }
  const value: Ctx = {
    me: q.data ?? null,
    isLoading: q.isLoading,
    login: async (email, password) => { await api('/auth/login', { method: 'POST', body: { email, password } }); await refresh() },
    logout: async () => { await api('/auth/logout', { method: 'POST' }); await refresh() },
    refresh,
  }
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth(): Ctx {
  const v = useContext(AuthCtx)
  if (!v) throw new Error('useAuth вне AuthProvider')
  return v
}
