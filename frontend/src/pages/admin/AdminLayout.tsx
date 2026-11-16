import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'

type Props = {
  titulo: string
  voltarPara?: string          // caminho do botão "voltar"
  rotuloVoltar?: string        // texto do botão "voltar"
  children: ReactNode
}

export function AdminLayout({ titulo, voltarPara, rotuloVoltar, children }: Props) {
  const navigate = useNavigate()
  const { usuario, logout } = useAuth()

  return (
    <div className="min-h-screen">
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {voltarPara !== undefined && (
              <button
                onClick={() => navigate(voltarPara)}
                className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
              >
                ← {rotuloVoltar ?? 'Voltar'}
              </button>
            )}
            <h1 className="text-lg font-semibold">{titulo}</h1>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-right">
              <div className="font-medium">{usuario?.nome_completo}</div>
              <div className="text-slate-500 dark:text-slate-400 text-xs">
                @{usuario?.username}
                <span className="ml-2 px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-[10px] font-semibold uppercase">
                  admin
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
    </div>
  )
}
