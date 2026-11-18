import { api } from './client'
import { FiltrosLivrePayload } from './relatorioLivre'
import { FiltrosPayload } from './relatorios'

/**
 * Cliente da API /jobs — extração assíncrona (Etapa 11).
 *
 * Fluxo típico:
 *   1. criar*()      → recebe JobCriadoResponse com job_id
 *   2. polling via obterJob(id)  (a cada 2s)  enquanto status estiver ativo
 *   3. baixarJob(id) quando status = 'concluido'
 *   4. opcional:   cancelarJob(id) enquanto status = 'pendente'
 */

export type JobStatus =
  | 'pendente'
  | 'conectando'
  | 'consultando'
  | 'tratando'
  | 'escrevendo'
  | 'concluido'
  | 'erro'
  | 'cancelado'

export const STATUS_ATIVOS: ReadonlySet<JobStatus> = new Set([
  'pendente',
  'conectando',
  'consultando',
  'tratando',
  'escrevendo',
])

export const STATUS_FINAIS: ReadonlySet<JobStatus> = new Set([
  'concluido',
  'erro',
  'cancelado',
])

export type JobResumo = {
  id: string
  usuario_id: number | null
  username: string | null
  tipo: 'relatorio_pronto' | 'relatorio_livre' | 'codigo_sql'
  relatorio_id: string
  titulo: string
  status: JobStatus
  progresso_pct: number
  total_linhas: number | null
  tamanho_bytes: number | null
  nome_arquivo: string | null
  erro_mensagem: string | null
  duracao_estimada_s: number | null
  criado_em: string            // ISO
  iniciado_em: string | null   // ISO
  concluido_em: string | null  // ISO
}

export type JobCriadoResponse = {
  job_id: string
  status: JobStatus
  posicao_fila: number | null
  mensagem: string
}

// ---- Criação (-async) ----

export async function criarJobRelatorio(
  relatorioId: string,
  payload: FiltrosPayload,
): Promise<JobCriadoResponse> {
  const resp = await api.post<JobCriadoResponse>(
    `/jobs/relatorios/${encodeURIComponent(relatorioId)}/extrair-async`,
    payload,
  )
  return resp.data
}

export async function criarJobLivre(
  filtros: FiltrosLivrePayload,
): Promise<JobCriadoResponse> {
  const resp = await api.post<JobCriadoResponse>(
    '/jobs/relatorio-livre/extrair-async',
    filtros,
  )
  return resp.data
}

export async function criarJobSql(
  sql: string,
  nomeArquivo?: string,
): Promise<JobCriadoResponse> {
  const resp = await api.post<JobCriadoResponse>(
    '/jobs/sql-livre/executar-async',
    { sql, nome_arquivo: nomeArquivo || 'consulta_sql.csv' },
  )
  return resp.data
}

// ---- Consultas ----

export async function listarJobs(todos = false): Promise<JobResumo[]> {
  const resp = await api.get<JobResumo[]>('/jobs', { params: { todos } })
  return resp.data
}

export async function obterJob(id: string): Promise<JobResumo> {
  const resp = await api.get<JobResumo>(`/jobs/${encodeURIComponent(id)}`)
  return resp.data
}

// ---- Cancelamento ----

export async function cancelarJob(id: string): Promise<void> {
  await api.delete(`/jobs/${encodeURIComponent(id)}`)
}

// ---- Download ----

/**
 * Baixa o CSV de um job concluído. Faz blob + dispara <a download>, igual os
 * outros endpoints de download. Usa o nome vindo do Content-Disposition.
 */
export async function baixarJob(id: string, fallbackNome = 'relatorio.csv'): Promise<void> {
  const resp = await api.get(`/jobs/${encodeURIComponent(id)}/download`, {
    responseType: 'blob',
    timeout: 60_000,
  })

  const nome = extrairNomeArquivo(
    resp.headers['content-disposition'] as string | undefined,
    fallbackNome,
  )

  const blob = new Blob([resp.data], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function extrairNomeArquivo(header: string | undefined, fallback: string): string {
  if (!header) return fallback
  const match = header.match(/filename="?([^"]+)"?/i)
  return match ? match[1] : fallback
}
