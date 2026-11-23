import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  Download,
  FileCode2,
  KeyRound,
  Loader2,
  PauseCircle,
  Pencil,
  Play,
  RefreshCw,
  Trash2,
  XCircle,
} from 'lucide-react'
import {
  AgendamentoCriadoResponse,
  AgendamentoResumo,
  apagarAgendamento,
  baixarExecucao,
  ExecucaoResumo,
  ExecucaoStatus,
  gerarScript,
  labelFrequencia,
  listarAgendamentos,
  listarExecucoes,
  PRESETS_LABELS,
  regenerarToken,
  ScriptGerado,
  testarAgendamento,
} from '../api/agendamentos'
import { mensagemErro } from '../api/client'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { ScriptDownloadModal } from '../components/ScriptDownloadModal'
import { Skeleton } from '../components/ui/skeleton'
import { TokenModal } from '../components/TokenModal'
import { useToast } from '../lib/toast'
import { cn } from '../lib/utils'

/**
 * Página de detalhes de um agendamento.
 *
 * Seções:
 *   1. Info — nome, descricao, schedule, próxima exec, botão testar/editar
 *   2. Token & script — regenerar token + baixar script com passo-a-passo
 *   3. Histórico de execuções — última N, com baixar CSV por linha
 *
 * Polling leve de 10s nas execuções enquanto houver uma pendente.
 */
export default function AgendamentoDetalhe() {
  const navigate = useNavigate()
  const params = useParams<{ id: string }>()
  const id = Number(params.id)
  const { toast } = useToast()

  const [ag, setAg] = useState<AgendamentoResumo | null>(null)
  const [execs, setExecs] = useState<ExecucaoResumo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [testando, setTestando] = useState(false)
  const [regerando, setRegerando] = useState(false)
  const [gerandoScript, setGerandoScript] = useState(false)

  // Modal do script e do token (regerado)
  const [tokenRegerado, setTokenRegerado] = useState<AgendamentoCriadoResponse | null>(null)
  const [scriptGerado, setScriptGerado] = useState<ScriptGerado | null>(null)

  // -------- carga --------
  const recarregar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarregando(true)
    try {
      const [ags, es] = await Promise.all([
        listarAgendamentos(),
        listarExecucoes(id, 50),
      ])
      const achado = ags.find((a) => a.id === id) ?? null
      setAg(achado)
      setExecs(es)
      setErro(null)
    } catch (e) {
      setErro(mensagemErro(e, 'Falha ao carregar o agendamento.'))
    } finally {
      if (!silencioso) setCarregando(false)
    }
  }, [id])

  useEffect(() => {
    recarregar()
  }, [recarregar])

  // Polling enquanto houver execução pendente (típico pós-testar)
  const temPendente = execs.some((e) => e.status === 'pendente')
  useEffect(() => {
    if (!temPendente) return
    const t = setInterval(() => recarregar(true), 10_000)
    return () => clearInterval(t)
  }, [temPendente, recarregar])

  // -------- ações --------
  const testar = async () => {
    setTestando(true)
    try {
      await testarAgendamento(id)
      toast({
        title: 'Disparado',
        description: 'A execução foi enfileirada; acompanhe no histórico.',
        variant: 'success',
      })
      await recarregar(true)
    } catch (e) {
      toast({
        title: 'Falha ao disparar',
        description: mensagemErro(e, 'Tente novamente em instantes.'),
        variant: 'destructive',
      })
    } finally {
      setTestando(false)
    }
  }

  const regerar = async () => {
    if (!window.confirm(
      'Vai regerar o token do agendamento. O script antigo para de funcionar — você precisará baixar e instalar o novo. Continuar?',
    )) return
    setRegerando(true)
    try {
      const r = await regenerarToken(id)
      setTokenRegerado(r)
      await recarregar(true)
    } catch (e) {
      toast({
        title: 'Falha ao regerar',
        description: mensagemErro(e),
        variant: 'destructive',
      })
    } finally {
      setRegerando(false)
    }
  }

  const baixarScriptClick = async () => {
    const tokenClaro = window.prompt(
      'Pra baixar o script, cole aqui o token em claro recebido na criação ou na última regeração:\n\n' +
      '(Se não tiver mais o token, use "Regerar token" primeiro.)',
    )
    if (!tokenClaro) return
    setGerandoScript(true)
    try {
      const s = await gerarScript(id, tokenClaro.trim())
      setScriptGerado(s)
    } catch (e) {
      toast({
        title: 'Falha ao gerar script',
        description: mensagemErro(e, 'Verifique se o token colado está correto.'),
        variant: 'destructive',
      })
    } finally {
      setGerandoScript(false)
    }
  }

  const apagar = async () => {
    if (!window.confirm(
      'Apagar este agendamento permanentemente? Esta ação não pode ser desfeita, e o histórico de execuções também será removido.',
    )) return
    try {
      await apagarAgendamento(id)
      toast({ title: 'Agendamento apagado', variant: 'default' })
      navigate('/agendamentos')
    } catch (e) {
      toast({
        title: 'Falha ao apagar',
        description: mensagemErro(e),
        variant: 'destructive',
      })
    }
  }

  // -------- render --------
  if (carregando) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8 md:py-10">
        <Skeleton className="h-8 w-56 mb-4" />
        <Skeleton className="h-48 rounded-lg mb-4" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    )
  }

  if (erro || !ag) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8 md:py-10">
        <button
          onClick={() => navigate('/agendamentos')}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>Agendamentos</span>
        </button>
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {erro ?? 'Agendamento não encontrado.'}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/agendamentos')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Agendamentos</span>
      </button>

      {/* === 1. Info principal === */}
      <div className="mb-6 flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight">{ag.nome}</h1>
            {!ag.ativo && (
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                pausado
              </span>
            )}
          </div>
          {ag.descricao && (
            <p className="text-sm text-muted-foreground mt-1">{ag.descricao}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" onClick={() => navigate(`/agendamentos/${id}/editar`)}>
            <Pencil className="h-4 w-4" />
            Editar
          </Button>
          <Button
            variant="outline"
            onClick={apagar}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
            Apagar
          </Button>
        </div>
      </div>

      <Card className="p-5 mb-6">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <Item rotulo="Relatório"><span className="font-mono">{ag.relatorio_id}</span></Item>
          <Item rotulo="Frequência">{labelFrequencia(ag)}</Item>
          {ag.preset_datas && (
            <Item rotulo="Período">{PRESETS_LABELS[ag.preset_datas]}</Item>
          )}
          {ag.filtros_base?.filial && (
            <Item rotulo="Filial">
              <span className="font-mono">{String(ag.filtros_base.filial)}</span>
            </Item>
          )}
          <Item rotulo="Próxima execução">
            {ag.ativo && ag.proxima_execucao
              ? formatarCompleto(ag.proxima_execucao)
              : <span className="text-muted-foreground">—</span>}
          </Item>
          <Item rotulo="Última execução">
            {ag.ultima_execucao
              ? formatarCompleto(ag.ultima_execucao)
              : <span className="text-muted-foreground">nunca</span>}
          </Item>
          <Item rotulo="Retenção do CSV">{ag.retencao_dias} dias</Item>
          <Item rotulo="Nome de arquivo">
            {ag.estrategia_nome === 'padrao' ? 'Sempre novo' : 'Sobrescreve'}
          </Item>
        </dl>

        <div className="mt-5 flex gap-2 flex-wrap">
          <Button onClick={testar} disabled={testando || !ag.ativo}>
            <Play className="h-4 w-4" />
            {testando ? 'Disparando...' : 'Testar agora'}
          </Button>
        </div>
      </Card>

      {/* === 2. Token & Script === */}
      <Card className="p-5 mb-6">
        <h2 className="text-base font-semibold mb-1">Script sincronizador</h2>
        <p className="text-xs text-muted-foreground mb-4">
          Instale esse script no PC pra receber os CSVs automaticamente na pasta que
          você escolher. Ele roda de hora em hora e baixa só o que ainda não baixou.
        </p>

        <div className="rounded-md border border-border bg-muted/30 px-3 py-2 mb-4 text-xs">
          <span className="text-muted-foreground mr-2">Token (prefixo):</span>
          <span className="font-mono">{ag.token_prefixo ?? '(sem token)'}</span>
          <span className="text-muted-foreground ml-2">
            — o token completo só é mostrado uma vez. Guarde ao criar ou regere.
          </span>
        </div>

        <div className="flex gap-2 flex-wrap">
          <Button onClick={baixarScriptClick} disabled={gerandoScript}>
            <FileCode2 className="h-4 w-4" />
            {gerandoScript ? 'Gerando...' : 'Baixar script'}
          </Button>
          <Button variant="outline" onClick={regerar} disabled={regerando}>
            <KeyRound className="h-4 w-4" />
            {regerando ? 'Regerando...' : 'Regerar token'}
          </Button>
        </div>
      </Card>

      {/* === 3. Histórico === */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-base font-semibold">Histórico de execuções</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => recarregar(true)}
        >
          <RefreshCw className="h-4 w-4" />
          Atualizar
        </Button>
      </div>

      {execs.length === 0 && (
        <Card className="p-8 text-center text-muted-foreground text-sm">
          Nenhuma execução ainda. Clique em <strong>Testar agora</strong> pra
          disparar a primeira.
        </Card>
      )}

      {execs.length > 0 && (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border">
            {execs.map((e) => (
              <ExecucaoLinha
                key={e.id}
                exec={e}
                agId={id}
              />
            ))}
          </ul>
        </Card>
      )}

      {/* Modais */}
      {tokenRegerado && (
        <TokenModal
          tokenClaro={tokenRegerado.token_claro}
          acabouDeRegerar
          onFechar={() => setTokenRegerado(null)}
        />
      )}
      {scriptGerado && (
        <ScriptDownloadModal
          script={scriptGerado}
          onFechar={() => setScriptGerado(null)}
        />
      )}
    </div>
  )
}

// =============================================================================
// Item de execução
// =============================================================================

function ExecucaoLinha({ exec, agId }: { exec: ExecucaoResumo; agId: number }) {
  const { toast } = useToast()
  const [baixando, setBaixando] = useState(false)

  const baixar = async () => {
    setBaixando(true)
    try {
      await baixarExecucao(agId, exec.id, exec.nome_arquivo ?? `execucao_${exec.id}.csv`)
    } catch (e) {
      toast({
        title: 'Falha ao baixar',
        description: mensagemErro(e, 'Arquivo pode ter expirado.'),
        variant: 'destructive',
      })
    } finally {
      setBaixando(false)
    }
  }

  const criado = formatarCompleto(exec.criado_em)
  const duracao = formatarDuracao(exec)
  const quantMaquinas = (exec.baixada_por ?? []).length

  return (
    <li className="px-4 py-3 flex items-start gap-3">
      <StatusBadge status={exec.status} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate">
          {exec.nome_arquivo ?? `execução ${exec.id}`}
        </div>
        <div className="text-xs text-muted-foreground flex items-center flex-wrap gap-x-2 mt-0.5">
          <span>{criado}</span>
          {duracao && <span>· {duracao}</span>}
          {exec.total_linhas != null && (
            <span>· {exec.total_linhas.toLocaleString('pt-BR')} linha(s)</span>
          )}
          {quantMaquinas > 0 && (
            <span>· baixada em {quantMaquinas} máquina{quantMaquinas > 1 ? 's' : ''}</span>
          )}
        </div>
        {exec.status === 'erro' && exec.erro_mensagem && (
          <div className="mt-1.5 text-xs text-destructive flex items-start gap-1">
            <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
            <span className="break-words">{exec.erro_mensagem}</span>
          </div>
        )}
      </div>
      {exec.status === 'concluida' && (
        <Button size="sm" variant="outline" onClick={baixar} disabled={baixando}>
          <Download className="h-4 w-4" />
          {baixando ? 'Baixando...' : 'Baixar'}
        </Button>
      )}
    </li>
  )
}

// =============================================================================
// Pequenos
// =============================================================================

function Item({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{rotulo}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  )
}

const BADGES: Record<ExecucaoStatus, { texto: string; classe: string; Icone: React.ElementType }> = {
  pendente:  { texto: 'Em execução', classe: 'bg-primary/15 text-primary',                   Icone: Loader2 },
  concluida: { texto: 'Concluída',   classe: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400', Icone: CheckCircle2 },
  erro:      { texto: 'Erro',        classe: 'bg-destructive/15 text-destructive',           Icone: XCircle },
  cancelada: { texto: 'Cancelada',   classe: 'bg-muted text-muted-foreground',               Icone: PauseCircle },
}

function StatusBadge({ status }: { status: ExecucaoStatus }) {
  const b = BADGES[status]
  const spin = status === 'pendente'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium shrink-0 mt-0.5',
        b.classe,
      )}
    >
      <b.Icone className={cn('h-3 w-3', spin && 'animate-spin')} />
      {b.texto}
    </span>
  )
}

function formatarCompleto(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatarDuracao(e: ExecucaoResumo): string | null {
  if (!e.concluido_em) return null
  try {
    const fim = new Date(e.concluido_em).getTime()
    const ini = new Date(e.criado_em).getTime()
    const s = Math.round((fim - ini) / 1000)
    if (s < 1) return null
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  } catch {
    return null
  }
}

