import { ReactNode } from 'react'
import { Sidebar } from './Sidebar'

/**
 * Layout padrão das páginas autenticadas: sidebar fixa à esquerda + área
 * de conteúdo flex que preenche o restante.
 *
 * Em mobile (<768px) a sidebar vira drawer com botão hamburger — o espaçamento
 * principal só é aplicado em md+.
 */
export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="md:pl-64">
        {children}
      </main>
    </div>
  )
}
