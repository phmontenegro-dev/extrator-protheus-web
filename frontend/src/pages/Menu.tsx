import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { listarRelatorios, RelatorioInfo } from '../api/relatorios'
import { mensagemErro } from '../api/client'

export default function Menu() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true
    listarRelatorios()
      .then((r) => {
        if (ativo) setRelatorios(r)
      })
      .catch((e) => {
        if (ativo) setErro(mensagemErro(e, 'Não foi possível carregar os relatórios.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <div className="min-h-screen">
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold">Extrator Protheus</h1>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-right">
              <div className="font-medium">{usuario?.nome_completo}</div>
              <div className="text-slate-500 dark:text-slate-400 text-xs">
                @{usuario?.username}
                {usuario?.is_admin && (
                  <span className="ml-2 px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-[10px] font-semibold uppercase">
                    admin
                  </span>
                )}
              </div>
            </div>
            {usuario?.is_admin && (
              <button
                onClick={() => navigate('/admin')}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
              >
                Admin
              </button>
            )}
            <button
              onClick={logout}
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        <h2 className="text-xl font-semibold mb-4">Relatórios disponíveis</h2>

        {carregando && <p className="text-slate-500">Carregando relatórios...</p>}

        {erro && (
          <div
            role="alert"
            className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-4"
          >
            {erro}
          </div>
        )}

        {!carregando && !erro && relatorios.length === 0 && (
          <p className="text-slate-500">
            Nenhum relatório disponível para seu usuário.
          </p>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {relatorios.map((r) => (
            <button
              key={r.id}
              onClick={() => navigate(`/relatorios/${r.id}`)}
              className="text-left bg-white dark:bg-slate-900 rounded-xl shadow p-5 hover:shadow-md transition border border-transparent hover:border-slate-300 dark:hover:border-slate-700"
            >
              <div className="font-semibold mb-1">{r.nome}</div>
              <div className="text-sm text-slate-500 dark:text-slate-400">
                {r.descricao}
              </div>
            </button>
          ))}
        </div>
      </main>
    </div>
  )
}
