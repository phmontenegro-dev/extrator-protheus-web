import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import * as authApi from '../api/auth'
import type { Usuario } from '../api/auth'

/**
 * Estado global de autenticação.
 *
 *   carregando: true enquanto consultamos /auth/me no bootstrap da app.
 *               Enquanto true, as rotas protegidas não decidem nada (evita
 *               flash de login antes do /me responder).
 *   usuario:    null se não autenticado; objeto Usuario se autenticado.
 */
type AuthContextValue = {
  carregando: boolean
  usuario: Usuario | null
  login: (username: string, senha: string) => Promise<void>
  logout: () => Promise<void>
  /**
   * Refaz GET /auth/me e atualiza o estado — usado após editar o perfil
   * próprio pra o header/sidebar pegarem o novo nome.
   */
  recarregar: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [carregando, setCarregando] = useState(true)
  const [usuario, setUsuario] = useState<Usuario | null>(null)

  useEffect(() => {
    let ativo = true
    authApi.me().then((u) => {
      if (ativo) {
        setUsuario(u)
        setCarregando(false)
      }
    })
    return () => {
      ativo = false
    }
  }, [])

  const login = async (username: string, senha: string) => {
    const u = await authApi.login(username, senha)
    setUsuario(u)
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } finally {
      // Mesmo que o backend falhe, zera o estado local — o usuário quis sair.
      setUsuario(null)
    }
  }

  const recarregar = async () => {
    const u = await authApi.me()
    setUsuario(u)
  }

  return (
    <AuthContext.Provider value={{ carregando, usuario, login, logout, recarregar }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (ctx === undefined) {
    throw new Error('useAuth precisa ser usado dentro de <AuthProvider>.')
  }
  return ctx
}
