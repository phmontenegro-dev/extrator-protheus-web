import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  PauseCircle,
  Plus,
} from 'lucide-react'
import {
  AgendamentoResumo,
  labelFrequencia,
  listarAgendamentos,
  PRESETS_LABELS,
} from '../api/agendamentos'
import { mensagemErro } from '../api/client'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'

/**
 * Lista todos os agendamentos do usuário (admin vê todos — endpoint já filtra).
 *
 * A "próxima execução" é formatada de forma amigável ("em 3h", "amanhã às 08:00")
 * pra reduzir carga cognitiva. Status visual: ativo (verde), inativo (cinza).
 */
export default function Agendamentos() {
  const navigate = useNavigate()
  const [itens, setItens] = useState<AgendamentoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true
    listarAgendamentos()
      .then((rs) => {
        if (ativo) setItens(rs)
      })
      .catch((e) => {
        if (ativo) setErro(mensagemErro(e, 'Não foi possível carregar os agendamentos.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/menu')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Menu</span>
      </button>

      <div className="mb-6 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Agendamentos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Relatórios que rodam automaticamente em horários recorrentes.
          </p>
        </div>
        <Button onClick={() => navigate('/agendamentos/novo')}>
          <Plus className="h-4 w-4" />
          Novo agendamento
        </Button>
      </div>

      {carregando && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
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

      {!carregando && !erro && itens.length === 0 && (
        <Card className="p-10 text-center text-muted-foreground">
          <Calendar className="h-12 w-12 mx-auto mb-3 opacity-40" />
          <p className="text-base">Nenhum agendamento criado ainda.</p>
          <p className="text-sm mt-1">
            Clique em <strong>Novo agendamento</strong> pra configurar uma recorrência.
          </p>
        </Card>
      )}

      {!carregando && !erro && itens.length > 0 && (
        <div className="space-y-2">
          {itens.map((ag) => (
            <Linha key={ag.id} ag={ag} />
          ))}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Linha de agendamento
// =============================================================================

function Linha({ ag }: { ag: AgendamentoResumo }) {
  const navigate = useNavigate()

  const preset = ag.preset_datas ? PRESETS_LABELS[ag.preset_datas] : null
  const proxima = formatarProxima(ag.proxima_execucao)
  const ultima = ag.ultima_execucao ? formatarRelativoCurto(ag.ultima_execucao) : null

  return (
    <button
      onClick={() => navigate(`/agendamentos/${ag.id}`)}
      className="text-left w-full"
    >
      <Card
        className={cn(
          'p-4 hover:shadow-md hover:border-primary/40 transition-all',
          !ag.ativo && 'opacity-60',
        )}
      >
        <div className="flex items-start gap-3">
          {/* Ícone de status */}
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
              ag.ativo ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
            )}
          >
            {ag.ativo ? <CheckCircle2 className="h-5 w-5" /> : <PauseCircle className="h-5 w-5" />}
          </div>

          {/* Corpo */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="font-semibold truncate">{ag.nome}</div>
              {!ag.ativo && (
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                  pausado
                </span>
              )}
            </div>
            {ag.descricao && (
              <div className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                {ag.descricao}
              </div>
            )}

            <div className="mt-2 flex items-center gap-x-3 gap-y-1 flex-wrap text-xs text-muted-foreground">
              <span className="font-mono">{ag.relatorio_id}</span>
              <span className="opacity-50">·</span>
              <span>{labelFrequencia(ag)}</span>
              {preset && (
                <>
                  <span className="opacity-50">·</span>
                  <span>{preset}</span>
                </>
              )}
            </div>
          </div>

          {/* Coluna direita — próxima execução */}
          <div className="shrink-0 text-right flex flex-col items-end gap-1">
            {ag.ativo && proxima && (
              <div className="flex items-center gap-1 text-sm">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                <span>{proxima}</span>
              </div>
            )}
            {ultima && (
              <div className="text-[11px] text-muted-foreground">
                Última: {ultima}
              </div>
            )}
            <ChevronRight className="h-4 w-4 text-muted-foreground mt-1" />
          </div>
        </div>
      </Card>
    </button>
  )
}

// =============================================================================
// Formatadores
// =============================================================================

function formatarProxima(iso: string | null): string | null {
  if (!iso) return null
  try {
    const d = new Date(iso)
    const agora = new Date()
    const diffMs = d.getTime() - agora.getTime()
    if (diffMs < 0) return 'Agora'
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'Em instantes'
    if (diffMin < 60) return `Em ${diffMin} min`
    const diffH = Math.floor(diffMin / 60)
    if (diffH < 24) return `Em ${diffH}h`
    const diffD = Math.floor(diffH / 24)
    if (diffD === 1) return `Amanhã às ${hora(d)}`
    if (diffD < 7) return `Em ${diffD} dias`
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ` às ${hora(d)}`
  } catch {
    return iso
  }
}

function formatarRelativoCurto(iso: string): string {
  try {
    const d = new Date(iso)
    const agora = new Date()
    const diffMin = Math.floor((agora.getTime() - d.getTime()) / 60000)
    if (diffMin < 1) return 'agora'
    if (diffMin < 60) return `${diffMin} min atrás`
    const diffH = Math.floor(diffMin / 60)
    if (diffH < 24) return `${diffH}h atrás`
    const diffD = Math.floor(diffH / 24)
    if (diffD < 7) return `${diffD}d atrás`
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  } catch {
    return iso
  }
}

function hora(d: Date): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

