import { useEffect, useState } from 'react'
import { AlertCircle, Check, X } from 'lucide-react'
import { AdminLayout } from './AdminLayout'
import { listarLogs, LogItem, LogsFiltros } from '../../api/admin'
import { mensagemErro } from '../../api/client'
import { Button } from '../../components/ui/button'
import { Card } from '../../components/ui/card'
import { Input } from '../../components/ui/input'

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
    setFiltros({ ...filtros, ...patch, offset: 0 })
  }

  const totalPaginas = Math.max(1, Math.ceil(total / LIMITE))
  const paginaAtual = Math.floor((filtros.offset ?? 0) / LIMITE) + 1

  return (
    <AdminLayout titulo="Logs de acesso" voltarPara="/admin" rotuloVoltar="Painel">
      {/* Filtros */}
      <Card className="p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div className="space-y-1">
            <label className="block text-xs font-medium">Username</label>
            <Input
              value={filtros.username ?? ''}
              onChange={(e) => atualizarFiltro({ username: e.target.value || undefined })}
              className="h-8"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-xs font-medium">Ação</label>
            <select
              value={filtros.acao ?? ''}
              onChange={(e) => atualizarFiltro({ acao: e.target.value || undefined })}
              className="w-full h-8 rounded-md border border-input bg-surface px-2 text-sm"
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
          <div className="space-y-1">
            <label className="block text-xs font-medium">Relatório</label>
            <Input
              value={filtros.relatorio_id ?? ''}
              onChange={(e) => atualizarFiltro({ relatorio_id: e.target.value || undefined })}
              placeholder="ct2010"
              className="h-8"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-xs font-medium">Período</label>
            <select
              value={filtros.desde_dias ?? 7}
              onChange={(e) => atualizarFiltro({ desde_dias: Number(e.target.value) })}
              className="w-full h-8 rounded-md border border-input bg-surface px-2 text-sm"
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
                onChange={(e) => atualizarFiltro({ somente_falhas: e.target.checked })}
                className="rounded"
              />
              Só falhas
            </label>
          </div>
        </div>
      </Card>

      {erro && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive mb-4">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}

      {/* Tabela */}
      <Card className="overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-muted text-left uppercase text-muted-foreground">
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
                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && itens.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                  Nenhum log encontrado para os filtros atuais.
                </td>
              </tr>
            )}
            {itens.map((l) => (
              <LinhaLog key={l.id} log={l} />
            ))}
          </tbody>
        </table>
      </Card>

      {/* Paginação */}
      {total > LIMITE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="text-muted-foreground">
            {total} registros — página {paginaAtual} de {totalPaginas}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setFiltros({
                  ...filtros,
                  offset: Math.max(0, (filtros.offset ?? 0) - LIMITE),
                })
              }
              disabled={(filtros.offset ?? 0) === 0}
            >
              ← Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setFiltros({
                  ...filtros,
                  offset: (filtros.offset ?? 0) + LIMITE,
                })
              }
              disabled={paginaAtual >= totalPaginas}
            >
              Próximo →
            </Button>
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
      <tr className="border-t border-border">
        <td className="px-3 py-2 whitespace-nowrap font-mono text-[11px]">
          {new Date(log.timestamp).toLocaleString('pt-BR')}
        </td>
        <td className="px-3 py-2 font-mono">{log.username ?? '—'}</td>
        <td className="px-3 py-2">{log.acao}</td>
        <td className="px-3 py-2 font-mono">{log.relatorio_id ?? '—'}</td>
        <td className="px-3 py-2 font-mono">{log.ip_origem ?? '—'}</td>
        <td className="px-3 py-2">
          {log.sucesso ? (
            <Check className="h-4 w-4 text-success" />
          ) : (
            <X className="h-4 w-4 text-destructive" />
          )}
        </td>
        <td className="px-3 py-2">
          {temDetalhes && (
            <button
              onClick={() => setExpandido((v) => !v)}
              className="text-primary hover:underline"
            >
              {expandido ? 'ocultar' : 'ver'}
            </button>
          )}
        </td>
      </tr>
      {expandido && (
        <tr className="bg-muted/50">
          <td colSpan={7} className="px-3 py-3">
            <dl className="grid grid-cols-1 md:grid-cols-4 gap-x-4 gap-y-2 text-xs">
              {log.registros_retornados != null && (
                <div>
                  <dt className="text-muted-foreground">Registros</dt>
                  <dd className="font-mono">{log.registros_retornados}</dd>
                </div>
              )}
              {log.duracao_ms != null && (
                <div>
                  <dt className="text-muted-foreground">Duração</dt>
                  <dd className="font-mono">{(log.duracao_ms / 1000).toFixed(1)}s</dd>
                </div>
              )}
              {log.erro_mensagem && (
                <div className="md:col-span-4">
                  <dt className="text-muted-foreground">Mensagem</dt>
                  <dd className="font-mono text-destructive break-words">
                    {log.erro_mensagem}
                  </dd>
                </div>
              )}
              {log.parametros && Object.keys(log.parametros).length > 0 && (
                <div className="md:col-span-4">
                  <dt className="text-muted-foreground">Parâmetros</dt>
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
