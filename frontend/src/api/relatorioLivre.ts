import { api } from './client'

export type TabelaInfo = {
  nome: string
  descricao: string | null
  campo_data_sugerido: string | null
}

export type ColunasResponse = {
  tabela: string
  colunas: string[]
}

export type FiltrosLivrePayload = {
  tabela: string
  colunas: string[]
  campo_data: string | null
  data_inicio: string | null
  data_fim: string | null
  max_linhas: number | null
}

export async function listarTabelas(): Promise<TabelaInfo[]> {
  const resp = await api.get<TabelaInfo[]>('/relatorio-livre/tabelas')
  return resp.data
}

export async function listarColunas(tabela: string): Promise<ColunasResponse> {
  const resp = await api.get<ColunasResponse>(
    `/relatorio-livre/colunas/${encodeURIComponent(tabela)}`,
  )
  return resp.data
}

/** Executa a extração livre e dispara o download do CSV. */
export async function extrairLivre(filtros: FiltrosLivrePayload): Promise<void> {
  const resp = await api.post('/relatorio-livre/extrair', filtros, {
    responseType: 'blob',
    timeout: 15 * 60 * 1000,
  })

  const nomeArquivo = extrairNomeArquivo(
    resp.headers['content-disposition'] as string | undefined,
    `${filtros.tabela}.csv`,
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
