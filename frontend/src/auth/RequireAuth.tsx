import { Navigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'
import { useAuth } from './AuthContext'

/**
 * Wrapper de rota que exige usuário autenticado.
 * Sem sessão -> redireciona para /login (guardando a rota original pra
 * voltar depois do login).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { carregando, usuario } = useAuth()
  const location = useLocation()

  if (carregando) return <TelaCarregando />
  if (!usuario) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  return <>{children}</>
}

/**
 * Inverso do RequireAuth: se já está logado, não deixa entrar na tela de
 * login. Manda pro menu (ou pra rota que o usuário originalmente queria).
 */
export function RedirectIfAuth({ children }: { children: ReactNode }) {
  const { carregando, usuario } = useAuth()
  const location = useLocation()

  if (carregando) return <TelaCarregando />
  if (usuario) {
    const destino = (location.state as { from?: string } | null)?.from ?? '/menu'
    return <Navigate to={destino} replace />
  }
  return <>{children}</>
}

function TelaCarregando() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-slate-500">Carregando...</div>
    </div>
  )
}
