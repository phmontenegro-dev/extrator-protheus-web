import { api } from './client'

/**
 * Cliente da API /agendamentos — recorrência de execuções (Etapa 14).
 *
 * Fluxo típico:
 *   1. criar()             → recebe AgendamentoCriadoResponse com token_claro
 *   2. (usuário copia o token / baixa o script)
 *   3. listar() / obter()  → polling leve, mostra próxima execução etc.
 *   4. listarExecucoes()   → histórico de disparos (pode baixar CSV de cada)
 *   5. testar()            → dispara agora sem alterar o cronograma
 *   6. editar() / apagar() / regenerarToken() conforme necessário
 */

export type Frequencia = 'diario' | 'semanal' | 'mensal'

export type PresetDatas =
  | 'ontem'
  | 'ultimos_7'
  | 'ultimos_30'
  | 'semana_anterior'
  | 'mes_anterior'
  | 'mes_atual_ate_ontem'

export const PRESETS_LABELS: Record<PresetDatas, string> = {
  ontem: 'Ontem',
  ultimos_7: 'Últimos 7 dias',
  ultimos_30: 'Últimos 30 dias',
  semana_anterior: 'Semana anterior (seg a dom)',
  mes_anterior: 'Mês anterior (completo)',
  mes_atual_ate_ontem: 'Mês atual até ontem',
}

export type TipoAgendamento = 'relatorio_pronto' | 'relatorio_livre' | 'codigo_sql'
export type EstrategiaNome = 'padrao' | 'sobrescrever'

export type AgendamentoResumo = {
  id: number
  usuario_id: number
  username: string | null
  nome: string
  descricao: string | null
  tipo: TipoAgendamento
  relatorio_id: string
  filtros_base: Record<string, unknown> | null
  sql_texto: string | null
  preset_datas: PresetDatas | null
  frequencia: Frequencia
  dias_semana: number[] | null
  dia_mes: number | null
  hora: number
  minuto: number
  ativo: boolean
  proxima_execucao: string | null
  ultima_execucao: string | null
  estrategia_nome: EstrategiaNome
  retencao_dias: number
  token_prefixo: string | null
  criado_em: string
  atualizado_em: string
}

export type AgendamentoCriadoResponse = AgendamentoResumo & {
  /** Token em claro — mostrado UMA VEZ e não é persistido no banco. */
  token_claro: string
}

export type AgendamentoPayload = {
  nome: string
  descricao?: string | null
  tipo: TipoAgendamento
  relatorio_id: string
  filtros_base?: Record<string, unknown> | null
  sql_texto?: string | null
  preset_datas?: PresetDatas | null
  frequencia: Frequencia
  dias_semana?: number[] | null
  dia_mes?: number | null
  hora: number
  minuto: number
  ativo?: boolean
  estrategia_nome?: EstrategiaNome
  retencao_dias?: number
}

export type ExecucaoStatus = 'pendente' | 'concluida' | 'erro' | 'cancelada'

export type ExecucaoResumo = {
  id: number
  agendamento_id: number
  job_id: string | null
  status: ExecucaoStatus
  params_resolvidos: Record<string, unknown> | null
  total_linhas: number | null
  tamanho_bytes: number | null
  nome_arquivo: string | null
  erro_mensagem: string | null
  baixada_por: string[] | null
  criado_em: string
  concluido_em: string | null
}

export type ScriptGerado = {
  nome_arquivo: string
  conteudo: string
  instrucoes: string
  extensao: string
}

// =============================================================================
// CRUD
// =============================================================================

export async function listarAgendamentos(): Promise<AgendamentoResumo[]> {
  const r = await api.get<AgendamentoResumo[]>('/agendamentos')
  return r.data
}

export async function criarAgendamento(
  payload: AgendamentoPayload,
): Promise<AgendamentoCriadoResponse> {
  const r = await api.post<AgendamentoCriadoResponse>('/agendamentos', payload)
  return r.data
}

export async function editarAgendamento(
  id: number,
  payload: AgendamentoPayload,
): Promise<AgendamentoResumo> {
  const r = await api.patch<AgendamentoResumo>(`/agendamentos/${id}`, payload)
  return r.data
}

export async function apagarAgendamento(id: number): Promise<void> {
  await api.delete(`/agendamentos/${id}`)
}

export async function regenerarToken(id: number): Promise<AgendamentoCriadoResponse> {
  const r = await api.post<AgendamentoCriadoResponse>(
    `/agendamentos/${id}/regenerar-token`,
  )
  return r.data
}

export async function testarAgendamento(id: number): Promise<ExecucaoResumo> {
  const r = await api.post<ExecucaoResumo>(`/agendamentos/${id}/testar`)
  return r.data
}

// =============================================================================
// Execuções
// =============================================================================

export async function listarExecucoes(
  agendamentoId: number,
  limite = 50,
): Promise<ExecucaoResumo[]> {
  const r = await api.get<ExecucaoResumo[]>(
    `/agendamentos/${agendamentoId}/execucoes`,
    { params: { limite } },
  )
  return r.data
}

/** Baixa o CSV de uma execução concluída (download direto). */
export async function baixarExecucao(
  agendamentoId: number,
  execucaoId: number,
  nomeFallback = 'relatorio.csv',
): Promise<void> {
  const r = await api.get(
    `/agendamentos/${agendamentoId}/execucoes/${execucaoId}/download`,
    { responseType: 'blob', timeout: 60_000 },
  )
  const nome =
    extrairNome(r.headers['content-disposition'] as string | undefined) ||
    nomeFallback

  const blob = new Blob([r.data], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// =============================================================================
// Script sincronizador
// =============================================================================

export async function gerarScript(
  id: number,
  tokenClaro: string,
  so: 'windows' | 'linux' | 'mac' = 'windows',
): Promise<ScriptGerado> {
  const r = await api.post<ScriptGerado>(
    `/agendamentos/${id}/script`,
    null,
    {
      params: { so },
      headers: { 'X-Token-Claro': tokenClaro },
    },
  )
  return r.data
}

// =============================================================================
// Helpers de UI
// =============================================================================

export function labelFrequencia(ag: AgendamentoResumo): string {
  const h = `${String(ag.hora).padStart(2, '0')}:${String(ag.minuto).padStart(2, '0')}`
  if (ag.frequencia === 'diario') return `Diário às ${h}`
  if (ag.frequencia === 'semanal') {
    const dias = DIAS_SEMANA_LABEL
    const sel = (ag.dias_semana ?? []).map((d) => dias[d - 1] ?? '?').join(', ')
    return `Semanal (${sel}) às ${h}`
  }
  if (ag.frequencia === 'mensal') return `Mensal dia ${ag.dia_mes} às ${h}`
  return ag.frequencia
}

export const DIAS_SEMANA_LABEL = [
  'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom',
] as const

// Helpers de parsing
function extrairNome(header: string | undefined): string | null {
  if (!header) return null
  const m = header.match(/filename="?([^"]+)"?/i)
  return m ? m[1] : null
}
