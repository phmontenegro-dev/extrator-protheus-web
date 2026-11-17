import { Navigate } from 'react-router-dom'
import { ReactNode } from 'react'
import { useAuth } from './AuthContext'

/**
 * Guard de rota administrativa.
 *
 * - Enquanto carrega a sessão, mostra tela neutra (evita flash).
 * - Sem sessão -> /login (o RequireAuth também faria isso; aqui atalhamos).
 * - Logado mas não-admin -> /menu (sem erro feio, só volta).
 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { carregando, usuario } = useAuth()

  if (carregando) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Carregando...</div>
      </div>
    )
  }
  if (!usuario) return <Navigate to="/login" replace />
  if (!usuario.is_admin) return <Navigate to="/menu" replace />
  return <>{children}</>
}
