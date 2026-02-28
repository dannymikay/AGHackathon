import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'

type Role = 'farmer' | 'buyer' | 'trucker' | null

interface AuthState {
  token: string | null
  role: Role
  userId: string | null
}

interface AuthContextValue extends AuthState {
  login: (token: string, role: Role, userId: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => ({
    token: localStorage.getItem('token'),
    role: localStorage.getItem('role') as Role,
    userId: localStorage.getItem('userId'),
  }))

  const login = (token: string, role: Role, userId: string) => {
    localStorage.setItem('token', token)
    localStorage.setItem('role', role ?? '')
    localStorage.setItem('userId', userId)
    setAuth({ token, role, userId })
  }

  const logout = () => {
    localStorage.clear()
    setAuth({ token: null, role: null, userId: null })
  }

  return (
    <AuthContext.Provider value={{ ...auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
