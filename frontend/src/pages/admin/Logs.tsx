import { useEffect, useState } from 'react'
import { AdminLayout } from './AdminLayout'
import { listarLogs, LogItem, LogsFiltros } from '../../api/admin'
import { mensagemErro } from '../../api/client'

const LIMITE = 50

export default function Logs() {
  const [filtros, setFiltros] = useState<LogsFiltros>({
    desde_dias: 7,
    limit: LIMITE,
    offset: 0,
  })
  const [itens, setItens] = useState<LogItem[]>([])
  const [total, setTotal] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = async (f: LogsFiltros) => {
    setCarregando(true)
    setErro(null)
    try {
      const resp = await listarLogs(f)
      setItens(resp.itens)
      setTotal(resp.total)
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível carregar os logs.'))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar(filtros)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtros])

  const atualizarFiltro = (patch: Partial<LogsFiltros>) => {
    // Qualquer mudança de filtro reseta a paginação.
    setFiltros({ ...filtros, ...patch, offset: 0 })
  }

  const totalPaginas = Math.max(1, Math.ceil(total / LIMITE))
  const paginaAtual = Math.floor((filtros.offset ?? 0) / LIMITE) + 1

  return (
    <AdminLayout titulo="Logs de acesso" voltarPara="/admin" rotuloVoltar="Painel">
      {/* Filtros */}
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div>
            <label className="block text-xs font-medium mb-1">Username</label>
            <input
              type="text"
              value={filtros.username ?? ''}
              onChange={(e) =>
                atualizarFiltro({ username: e.target.value || undefined })
              }
              className="w-full rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Ação</label>
            <select
              value={filtros.acao ?? ''}
              onChange={(e) =>
                atualizarFiltro({ acao: e.target.value || undefined })
              }
              className="w-full rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
            >
              <option value="">(todas)</option>
              <option value="login_ok">login_ok</option>
              <option value="login_falhou">login_falhou</option>
              <option value="logout">logout</option>
              <option value="extrair_relatorio">extrair_relatorio</option>
              <option value="acesso_negado">acesso_negado</option>
              <option value="admin_criou_usuario">admin_criou_usuario</option>
              <option value="admin_editou_usuario">admin_editou_usuario</option>
              <option value="admin_resetou_senha">admin_resetou_senha</option>
              <option value="admin_atualizou_permissoes">
                admin_atualizou_permissoes
              </option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Relatório</label>
            <input
              type="text"
              value={filtros.relatorio_id ?? ''}
              onChange={(e) =>
                atualizarFiltro({ relatorio_id: e.target.value || undefined })
              }
              placeholder="ct2010"
              className="w-full rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Período</label>
            <select
              value={filtros.desde_dias ?? 7}
              onChange={(e) =>
                atualizarFiltro({ desde_dias: Number(e.target.value) })
              }
              className="w-full rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
            >
              <option value={1}>24 horas</option>
              <option value={7}>7 dias</option>
              <option value={30}>30 dias</option>
              <option value={90}>90 dias</option>
              <option value={0}>Todos</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={filtros.somente_falhas ?? false}
                onChange={(e) =>
                  atualizarFiltro({ somente_falhas: e.target.checked })
                }
                className="rounded"
              />
              Só falhas
            </label>
          </div>
        </div>
      </div>

      {erro && (
        <div className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3 mb-4">
          {erro}
        </div>
      )}

      {/* Tabela */}
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 dark:bg-slate-800 text-left uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Quando</th>
              <th className="px-3 py-2">Usuário</th>
              <th className="px-3 py-2">Ação</th>
              <th className="px-3 py-2">Relatório</th>
              <th className="px-3 py-2">IP</th>
              <th className="px-3 py-2">OK</th>
              <th className="px-3 py-2">Detalhes</th>
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && itens.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                  Nenhum log encontrado para os filtros atuais.
                </td>
              </tr>
            )}
            {itens.map((l) => (
              <LinhaLog key={l.id} log={l} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {total > LIMITE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="text-slate-500">
            {total} registros — página {paginaAtual} de {totalPaginas}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() =>
                setFiltros({
                  ...filtros,
                  offset: Math.max(0, (filtros.offset ?? 0) - LIMITE),
                })
              }
              disabled={(filtros.offset ?? 0) === 0}
              className="px-3 py-1 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-50"
            >
              ← Anterior
            </button>
            <button
              onClick={() =>
                setFiltros({
                  ...filtros,
                  offset: (filtros.offset ?? 0) + LIMITE,
                })
              }
              disabled={paginaAtual >= totalPaginas}
              className="px-3 py-1 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-50"
            >
              Próximo →
            </button>
          </div>
        </div>
      )}
    </AdminLayout>
  )
}

function LinhaLog({ log }: { log: LogItem }) {
  const [expandido, setExpandido] = useState(false)
  const temDetalhes =
    (log.parametros && Object.keys(log.parametros).length > 0) ||
    log.erro_mensagem ||
    log.registros_retornados != null ||
    log.duracao_ms != null

  return (
    <>
      <tr className="border-t border-slate-100 dark:border-slate-800">
        <td className="px-3 py-2 whitespace-nowrap font-mono text-[11px]">
          {new Date(log.timestamp).toLocaleString('pt-BR')}
        </td>
        <td className="px-3 py-2 font-mono">{log.username ?? '—'}</td>
        <td className="px-3 py-2">{log.acao}</td>
        <td className="px-3 py-2 font-mono">{log.relatorio_id ?? '—'}</td>
        <td className="px-3 py-2 font-mono">{log.ip_origem ?? '—'}</td>
        <td className="px-3 py-2">
          {log.sucesso ? (
            <span className="text-emerald-600 dark:text-emerald-400">✓</span>
          ) : (
            <span className="text-red-600 dark:text-red-400">✗</span>
          )}
        </td>
        <td className="px-3 py-2">
          {temDetalhes && (
            <button
              onClick={() => setExpandido((v) => !v)}
              className="text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              {expandido ? 'ocultar' : 'ver'}
            </button>
          )}
        </td>
      </tr>
      {expandido && (
        <tr className="bg-slate-50 dark:bg-slate-800/50">
          <td colSpan={7} className="px-3 py-3">
            <dl className="grid grid-cols-1 md:grid-cols-4 gap-x-4 gap-y-2 text-xs">
              {log.registros_retornados != null && (
                <div>
                  <dt className="text-slate-500">Registros</dt>
                  <dd className="font-mono">{log.registros_retornados}</dd>
                </div>
              )}
              {log.duracao_ms != null && (
                <div>
                  <dt className="text-slate-500">Duração</dt>
                  <dd className="font-mono">{(log.duracao_ms / 1000).toFixed(1)}s</dd>
                </div>
              )}
              {log.erro_mensagem && (
                <div className="md:col-span-4">
                  <dt className="text-slate-500">Mensagem</dt>
                  <dd className="font-mono text-red-700 dark:text-red-400 break-words">
                    {log.erro_mensagem}
                  </dd>
                </div>
              )}
              {log.parametros && Object.keys(log.parametros).length > 0 && (
                <div className="md:col-span-4">
                  <dt className="text-slate-500">Parâmetros</dt>
                  <dd className="font-mono break-words whitespace-pre-wrap">
                    {JSON.stringify(log.parametros, null, 2)}
                  </dd>
                </div>
              )}
            </dl>
          </td>
        </tr>
      )}
    </>
  )
}
