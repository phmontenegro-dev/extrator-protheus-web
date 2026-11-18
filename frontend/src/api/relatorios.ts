import { api } from './client'

/** Tipos de filtros possíveis — espelha o registry do backend. */
export type TipoFiltro = 'nenhum' | 'periodo' | 'filial_periodo' | 'livre'

export type RelatorioInfo = {
  id: string
  nome: string
  descricao: string
  filtros: TipoFiltro
  // Área atribuída. null = relatório vai pra seção "Outros" no menu.
  area_id: number | null
  area_nome: string | null
  area_ordem: number | null
}

/** Payload enviado pro endpoint de extração. */
export type FiltrosPayload =
  | Record<string, never>                                                  // "nenhum"
  | { data_inicio: string; data_fim: string }                              // "periodo"
  | { filial: string; data_inicio: string; data_fim: string }              // "filial_periodo"

export async function listarRelatorios(): Promise<RelatorioInfo[]> {
  const resp = await api.get<RelatorioInfo[]>('/relatorios')
  return resp.data
}

/**
 * Executa um relatório e dispara o download do CSV.
 *
 * Funciona pra qualquer relatório do registry — o endpoint é derivado do id
 * (`/relatorios/{id}/extrair`). O payload varia conforme o tipo de filtro:
 *   - nenhum           → {}
 *   - periodo          → { data_inicio, data_fim }
 *   - filial_periodo   → { filial, data_inicio, data_fim }
 *
 * Como fazemos o download:
 *   - responseType 'blob' para receber bytes direto do servidor
 *   - lemos o filename do header Content-Disposition (o backend expõe
 *     esse header via Access-Control-Expose-Headers)
 *   - criamos URL temporária e disparamos um <a> hidden pro download
 *   - timeout de 15 min cobre os 10 min do Oracle (ORACLE_QUERY_TIMEOUT_S)
 */
export async function extrairRelatorio(
  id: string,
  filtros: FiltrosPayload,
): Promise<void> {
  const resp = await api.post(`/relatorios/${id}/extrair`, filtros, {
    responseType: 'blob',
    timeout: 15 * 60 * 1000,
  })

  const nomeArquivo = extrairNomeArquivo(
    resp.headers['content-disposition'] as string | undefined,
    `${id}.csv`,
  )

  const blob = new Blob([resp.data], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomeArquivo
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
