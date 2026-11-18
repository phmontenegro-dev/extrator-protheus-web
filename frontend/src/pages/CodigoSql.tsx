import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  ChevronLeft,
  Download,
  Play,
  TerminalSquare,
} from 'lucide-react'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { executarSql, SqlExecutarResponse } from '../api/sqlLivre'
import { criarJobSql } from '../api/jobs'
import { mensagemErro } from '../api/client'
import { useToast } from '../lib/toast'
import { cn } from '../lib/utils'

/**
 * Tela de execução de SQL livre (SELECT only).
 *
 * Fluxo:
 *   1. Usuário escreve um SELECT na textarea
 *   2. Executar → POST /sql-livre/executar → preview em tabela (até 500 linhas)
 *   3. Se trunc: aviso com botão "Baixar completo"
 *   4. Download CSV → POST /sql-livre/download → arquivo no disco
 *
 * O backend bloqueia qualquer SQL que não seja SELECT/WITH — erros vêm como
 * 422 com mensagem clara e aparecem inline + toast.
 */
export default function CodigoSql() {
  const navigate = useNavigate()
  const { toast } = useToast()

  const [sql, setSql] = useState('')
  const [resultado, setResultado] = useState<SqlExecutarResponse | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [executando, setExecutando] = useState(false)
  const [baixando, setBaixando] = useState(false)

  const executar = async () => {
    if (!sql.trim()) {
      setErro('Digite um SQL antes de executar.')
      return
    }
    setErro(null)
    setResultado(null)
    setExecutando(true)
    try {
      const r = await executarSql(sql)
      setResultado(r)
      toast({
        title: 'Consulta executada',
        description: `${r.total} linha(s) em ${(r.duracao_ms / 1000).toFixed(1)}s${r.truncado ? ' (truncado)' : ''}`,
        variant: 'success',
      })
    } catch (e) {
      const msg = mensagemErro(e, 'Falha na consulta.')
      setErro(msg)
      toast({
        title: 'Falha na execução',
        description: msg,
        variant: 'destructive',
      })
    } finally {
      setExecutando(false)
    }
  }

  const baixar = async () => {
    if (!sql.trim()) {
      setErro('Digite um SQL antes de baixar.')
      return
    }
    setErro(null)
    setBaixando(true)
    try {
      const r = await criarJobSql(sql)
      toast({
        title: 'Job criado',
        description: 'Acompanhe o progresso em "Meus jobs".',
        variant: 'success',
      })
      navigate(`/jobs?focus=${encodeURIComponent(r.job_id)}`)
    } catch (e) {
      const msg = mensagemErro(e, 'Falha ao enviar o job.')
      setErro(msg)
      toast({ title: 'Não foi possível enviar', description: msg, variant: 'destructive' })
      setBaixando(false)
    }
  }

  // Ctrl+Enter executa, igual terminal
  const atalho = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (!executando && !baixando) executar()
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/menu')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Menu</span>
      </button>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <TerminalSquare className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Código SQL</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Consulte diretamente o Oracle Protheus. Apenas <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">SELECT</code> e <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">WITH</code> são permitidos.
          Timeout de 4 minutos.
        </p>
      </div>

      {/* Aviso de segurança */}
      <div className="mb-4 flex items-start gap-3 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-primary" />
        <div>
          <p className="text-foreground">
            Toda consulta executada é <strong>registrada nos logs de acesso</strong> com o texto completo do SQL e duração.
          </p>
        </div>
      </div>

      {/* Editor */}
      <Card className="p-0 overflow-hidden mb-4">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted">
          <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
            <span>sql</span>
            <span className="opacity-50">·</span>
            <span className="hidden sm:inline">Ctrl+Enter executa</span>
          </div>
          <div className="text-xs text-muted-foreground">
            {sql.length}/50000
          </div>
        </div>
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={atalho}
          disabled={executando || baixando}
          spellCheck={false}
          placeholder={`SELECT a1_cod, a1_nome
FROM sa1010
WHERE rownum <= 100
  AND a1_nome LIKE '%KLABIN%'`}
          className="w-full min-h-[260px] px-4 py-3 bg-surface text-foreground font-mono text-sm resize-y focus:outline-none disabled:opacity-60"
        />
      </Card>

      {/* Botões */}
      <div className="flex flex-wrap gap-2 mb-6">
        <Button onClick={executar} disabled={executando || baixando}>
          <Play className="h-4 w-4" />
          {executando ? 'Executando...' : 'Executar (preview)'}
        </Button>
        <Button
          variant="outline"
          onClick={baixar}
          disabled={executando || baixando}
        >
          <Download className="h-4 w-4" />
          {baixando ? 'Enviando...' : 'Baixar CSV completo (background)'}
        </Button>
      </div>

      {/* Erro */}
      {erro && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span className="font-mono text-xs break-all">{erro}</span>
        </div>
      )}

      {/* Resultado */}
      {resultado && (
        <section>
          <div className="flex items-center justify-between mb-3 text-sm">
            <div className="text-muted-foreground">
              <span className="font-semibold text-foreground">{resultado.total}</span> linha(s) ·{' '}
              <span className="font-semibold text-foreground">
                {(resultado.duracao_ms / 1000).toFixed(1)}s
              </span>
              {resultado.truncado && (
                <span className="ml-2 text-primary">
                  · preview truncado — use "Baixar CSV completo" para ver tudo
                </span>
              )}
            </div>
          </div>

          <Card className="overflow-hidden">
            <div className="overflow-auto max-h-[600px]">
              <table className="w-full text-xs">
                <thead className="bg-muted sticky top-0">
                  <tr>
                    {resultado.colunas.map((c) => (
                      <th
                        key={c}
                        className="px-3 py-2 text-left font-semibold text-muted-foreground uppercase tracking-wider border-b border-border whitespace-nowrap"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultado.linhas.length === 0 && (
                    <tr>
                      <td
                        colSpan={Math.max(1, resultado.colunas.length)}
                        className="px-3 py-6 text-center text-muted-foreground"
                      >
                        Nenhum registro.
                      </td>
                    </tr>
                  )}
                  {resultado.linhas.map((linha, i) => (
                    <tr
                      key={i}
                      className={cn(
                        'border-b border-border last:border-0',
                        i % 2 === 1 && 'bg-muted/30',
                      )}
                    >
                      {linha.map((valor, j) => (
                        <td
                          key={j}
                          className="px-3 py-1.5 font-mono whitespace-nowrap max-w-[400px] overflow-hidden text-ellipsis"
                          title={valor == null ? '' : String(valor)}
                        >
                          {valor == null ? (
                            <span className="opacity-40 italic">null</span>
                          ) : (
                            String(valor)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      )}
    </div>
  )
}
