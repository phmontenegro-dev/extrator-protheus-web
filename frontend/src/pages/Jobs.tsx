import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Download,
  Loader2,
  Package,
  RefreshCw,
  ScrollText,
  Sparkles,
  TerminalSquare,
  Trash2,
  XCircle,
} from 'lucide-react'
import {
  baixarJob,
  cancelarJob,
  JobResumo,
  JobStatus,
  listarJobs,
  obterJob,
  STATUS_ATIVOS,
} from '../api/jobs'
import { mensagemErro } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { useToast } from '../lib/toast'
import { cn } from '../lib/utils'

/**
 * Página /jobs — "Meus jobs".
 *
 * Mostra os jobs assíncronos do usuário (ou de todos, se admin ligou o toggle).
 * Atualiza em tempo real com polling de 2s enquanto houver algum job ativo —
 * quando a lista toda vira estado final, o polling para.
 *
 * Deep-link: `/jobs?focus=<id>` destaca a linha (fundo diferente) por alguns
 * segundos, usado após criar um novo job pra guiar a atenção do usuário.
 */

const POLLING_INTERVAL_MS = 2000

export default function Jobs() {
  const navigate = useNavigate()
  const location = useLocation()
  const { usuario } = useAuth()
  const { toast } = useToast()

  const [jobs, setJobs] = useState<JobResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [verTodos, setVerTodos] = useState(false)
  const [atualizando, setAtualizando] = useState(false)

  // ID a destacar (vindo da querystring `?focus=xxx`), 6s de highlight.
  const focusId = useMemo(() => new URLSearchParams(location.search).get('focus'), [location.search])

  const carregar = useCallback(
    async (silencioso = false) => {
      if (!silencioso) setAtualizando(true)
      try {
        const lista = await listarJobs(verTodos && !!usuario?.is_admin)
        setJobs(lista)
        setErro(null)
      } catch (e) {
        setErro(mensagemErro(e, 'Falha ao listar jobs.'))
      } finally {
        if (!silencioso) setAtualizando(false)
        setCarregando(false)
      }
    },
    [verTodos, usuario?.is_admin],
  )

  // Bootstrap — recarrega quando toggle muda ou quando volto de criar.
  useEffect(() => {
    carregar()
  }, [carregar])

  // Polling enquanto houver jobs ativos.
  const temAtivo = useMemo(
    () => jobs.some((j) => STATUS_ATIVOS.has(j.status)),
    [jobs],
  )

  useEffect(() => {
    if (!temAtivo) return
    const t = setInterval(() => carregar(true), POLLING_INTERVAL_MS)
    return () => clearInterval(t)
  }, [temAtivo, carregar])

  const baixar = async (job: JobResumo) => {
    try {
      await baixarJob(job.id, job.nome_arquivo ?? `${job.id}.csv`)
      toast({
        title: 'Download iniciado',
        description: job.nome_arquivo ?? job.titulo,
        variant: 'success',
      })
    } catch (e) {
      toast({
        title: 'Falha ao baixar',
        description: mensagemErro(e, 'Arquivo pode ter expirado.'),
        variant: 'destructive',
      })
      carregar(true)
    }
  }

  const cancelar = async (job: JobResumo) => {
    if (!window.confirm(`Cancelar o job "${job.titulo}"?`)) return
    try {
      await cancelarJob(job.id)
      toast({ title: 'Job cancelado', variant: 'default' })
      carregar(true)
    } catch (e) {
      toast({
        title: 'Falha ao cancelar',
        description: mensagemErro(e, 'Talvez já tenha saído da fila.'),
        variant: 'destructive',
      })
      carregar(true)
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

      <div className="mb-6 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Meus jobs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Extrações que estão rodando em background. CSVs ficam disponíveis por 1 dia.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {usuario?.is_admin && (
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={verTodos}
                onChange={(e) => setVerTodos(e.target.checked)}
                className="rounded"
              />
              Ver de todos
            </label>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => carregar()}
            disabled={atualizando}
          >
            <RefreshCw className={cn('h-4 w-4', atualizando && 'animate-spin')} />
            Atualizar
          </Button>
        </div>
      </div>

      {carregando && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      )}

      {!carregando && erro && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {erro}
        </div>
      )}

      {!carregando && !erro && jobs.length === 0 && (
        <Card className="p-10 text-center text-muted-foreground">
          <Package className="h-12 w-12 mx-auto mb-3 opacity-40" />
          <p className="text-base">Nenhum job por aqui ainda.</p>
          <p className="text-sm mt-1">
            Volte ao <button className="underline" onClick={() => navigate('/menu')}>menu</button> e
            dispare uma extração — ela vai aparecer aqui.
          </p>
        </Card>
      )}

      {!carregando && !erro && jobs.length > 0 && (
        <Card className="overflow-hidden">
          {/* Cabeçalho desktop — só aparece em md+. Em mobile, os cards abaixo
              ficam empilhados sem precisar de header de tabela. */}
          <div className="hidden md:grid grid-cols-[1fr_140px_200px_200px] gap-3 px-4 py-2.5 bg-muted border-b border-border text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <div>Job</div>
            <div>Status</div>
            <div>Progresso</div>
            <div className="text-right">Ações</div>
          </div>

          <ul>
            {jobs.map((j) => (
              <JobLinha
                key={j.id}
                job={j}
                destaque={j.id === focusId}
                mostrarUsuario={verTodos && !!usuario?.is_admin}
                onBaixar={() => baixar(j)}
                onCancelar={() => cancelar(j)}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

// =============================================================================
// Linha de um job (tabela em desktop, card empilhado em mobile)
// =============================================================================

function JobLinha({
  job,
  destaque,
  mostrarUsuario,
  onBaixar,
  onCancelar,
}: {
  job: JobResumo
  destaque: boolean
  mostrarUsuario: boolean
  onBaixar: () => void
  onCancelar: () => void
}) {
  // Highlight some segundos, depois desliga — animação de atenção.
  const [destacado, setDestacado] = useState(destaque)
  const rodadaDestaque = useRef(0)
  useEffect(() => {
    if (!destaque) return
    rodadaDestaque.current += 1
    const rodada = rodadaDestaque.current
    setDestacado(true)
    const t = setTimeout(() => {
      if (rodadaDestaque.current === rodada) setDestacado(false)
    }, 6000)
    return () => clearTimeout(t)
  }, [destaque])

  const ativo = STATUS_ATIVOS.has(job.status)
  const concluido = job.status === 'concluido'
  const cancelavel = job.status === 'pendente'
  const Icone = iconeDoTipo(job.tipo, job.relatorio_id)

  const criado = formatarDataHora(job.criado_em)
  const duracao = formatarDuracao(job)

  return (
    <li
      className={cn(
        'border-b border-border last:border-0 transition-colors',
        'grid grid-cols-1 md:grid-cols-[1fr_140px_200px_200px] gap-3 px-4 py-3 items-center',
        destacado && 'bg-primary/10',
      )}
    >
      {/* Coluna 1 — identificação */}
      <div className="min-w-0">
        <div className="flex items-start gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
            <Icone className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-medium truncate">{job.titulo}</div>
            <div className="text-xs text-muted-foreground flex items-center flex-wrap gap-x-2">
              <span className="font-mono">{job.relatorio_id}</span>
              <span>· criado {criado}</span>
              {duracao && <span>· {duracao}</span>}
              {mostrarUsuario && job.username && (
                <span>· por <span className="font-mono">{job.username}</span></span>
              )}
              {concluido && job.total_linhas != null && (
                <span>· {job.total_linhas.toLocaleString('pt-BR')} linha(s)</span>
              )}
              {concluido && job.tamanho_bytes != null && (
                <span>· {formatarTamanho(job.tamanho_bytes)}</span>
              )}
            </div>
            {job.status === 'erro' && job.erro_mensagem && (
              <div className="mt-1.5 text-xs text-destructive flex items-start gap-1">
                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                <span className="break-words">{job.erro_mensagem}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Coluna 2 — status badge */}
      <div className="flex md:block">
        <StatusBadge status={job.status} />
      </div>

      {/* Coluna 3 — barra de progresso */}
      <div>
        <BarraProgresso
          pct={concluido ? 100 : job.progresso_pct}
          ativo={ativo}
          status={job.status}
          etaSegundos={job.duracao_estimada_s}
        />
      </div>

      {/* Coluna 4 — ações */}
      <div className="flex gap-2 justify-start md:justify-end">
        {concluido && (
          <Button size="sm" onClick={onBaixar}>
            <Download className="h-4 w-4" />
            Baixar
          </Button>
        )}
        {cancelavel && (
          <Button
            size="sm"
            variant="outline"
            onClick={onCancelar}
            className="text-destructive"
          >
            <Trash2 className="h-4 w-4" />
            Cancelar
          </Button>
        )}
      </div>
    </li>
  )
}

// =============================================================================
// Barra de progresso — determinada OU indeterminada
// =============================================================================

function BarraProgresso({
  pct,
  ativo,
  status,
  etaSegundos,
}: {
  pct: number
  ativo: boolean
  status: JobStatus
  etaSegundos: number | null
}) {
  const indeterminado = ativo && (etaSegundos == null || pct === 0)
  const corDaBarra = status === 'erro'
    ? 'bg-destructive'
    : status === 'cancelado'
      ? 'bg-muted-foreground'
      : 'bg-primary'

  return (
    <div className="space-y-1">
      <div className="relative h-2 w-full rounded-full bg-muted overflow-hidden">
        {indeterminado ? (
          // Barra "indeterminada" — animação CSS. Usa 30% da largura deslizando.
          <div
            className={cn('absolute inset-y-0 w-1/3 rounded-full', corDaBarra, 'animate-slide')}
            style={{ animation: 'barra-slide 1.5s ease-in-out infinite' }}
          />
        ) : (
          <div
            className={cn('h-full rounded-full transition-all duration-500', corDaBarra)}
            style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
          />
        )}
      </div>
      <div className="text-[10px] text-muted-foreground font-mono flex justify-between">
        <span>{indeterminado ? '...' : `${pct}%`}</span>
        {ativo && etaSegundos != null && (
          <span>~{etaSegundos}s estimados</span>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Badge de status
// =============================================================================

const ROTULOS: Record<JobStatus, { texto: string; classe: string; Icone: React.ElementType }> = {
  pendente: {
    texto: 'Na fila',
    classe: 'bg-muted text-muted-foreground',
    Icone: Clock,
  },
  conectando: {
    texto: 'Conectando',
    classe: 'bg-primary/15 text-primary',
    Icone: Loader2,
  },
  consultando: {
    texto: 'Consultando',
    classe: 'bg-primary/15 text-primary',
    Icone: Loader2,
  },
  tratando: {
    texto: 'Tratando',
    classe: 'bg-primary/15 text-primary',
    Icone: Loader2,
  },
  escrevendo: {
    texto: 'Escrevendo',
    classe: 'bg-primary/15 text-primary',
    Icone: Loader2,
  },
  concluido: {
    texto: 'Concluído',
    classe:
      'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
    Icone: CheckCircle2,
  },
  erro: {
    texto: 'Erro',
    classe: 'bg-destructive/15 text-destructive',
    Icone: XCircle,
  },
  cancelado: {
    texto: 'Cancelado',
    classe: 'bg-muted text-muted-foreground',
    Icone: XCircle,
  },
}

function StatusBadge({ status }: { status: JobStatus }) {
  const r = ROTULOS[status]
  const spin = STATUS_ATIVOS.has(status) && status !== 'pendente'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        r.classe,
      )}
    >
      <r.Icone className={cn('h-3 w-3', spin && 'animate-spin')} />
      {r.texto}
    </span>
  )
}

// =============================================================================
// Helpers
// =============================================================================

function iconeDoTipo(
  tipo: JobResumo['tipo'],
  relatorioId: string,
): React.ElementType {
  if (tipo === 'codigo_sql') return TerminalSquare
  if (tipo === 'relatorio_livre') return Sparkles
  // Pra relatório pronto, usa o mesmo mapa que o Menu — mantemos simples aqui.
  return ScrollText
  void relatorioId
}

function formatarDataHora(iso: string): string {
  try {
    const d = new Date(iso)
    const agora = new Date()
    const diffMs = agora.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'agora'
    if (diffMin < 60) return `há ${diffMin} min`
    const diffH = Math.floor(diffMin / 60)
    if (diffH < 24) return `há ${diffH}h`
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

function formatarDuracao(job: JobResumo): string | null {
  if (!job.iniciado_em) return null
  const fim = job.concluido_em ? new Date(job.concluido_em) : new Date()
  const ini = new Date(job.iniciado_em)
  const segs = Math.round((fim.getTime() - ini.getTime()) / 1000)
  if (segs < 1) return null
  if (segs < 60) return `${segs}s`
  const m = Math.floor(segs / 60)
  const s = segs % 60
  return `${m}m${s > 0 ? ` ${s}s` : ''}`
}

function formatarTamanho(bytes: number): string {
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(0)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

// Keyframe inline — Tailwind não vem com "indeterminate bar" pronto.
// Usamos CSS puro no index.css global, aqui é só a referência.
// Ver: @keyframes barra-slide em index.css.
