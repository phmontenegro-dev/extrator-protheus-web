import { api } from './client'

export type TabelaInfo = {
  nome: string
  descricao: string | null
  campo_data_sugerido: string | null
}

export type TipoLogico = 'texto' | 'numero' | 'data'

export type ColunaInfo = {
  nome: string
  tipo_oracle: string
  tipo_logico: TipoLogico
}

export type ColunasResponse = {
  tabela: string
  colunas: ColunaInfo[]
}

// Operadores — precisa casar com o Literal/schema do backend.
export type Operador =
  // texto
  | '=' | '<>' | 'contem' | 'comeca_com' | 'em_lista' | 'is_null' | 'nao_is_null'
  // numero
  | '>' | '<' | '>=' | '<=' | 'entre'
  // data
  | 'data_igual' | 'data_maior' | 'data_menor' | 'data_entre' | 'ultimos_n_dias'

/** Mesma tabela do backend — mantida aqui pra UI oferecer só o válido. */
export const OPERADORES_POR_TIPO: Record<TipoLogico, Operador[]> = {
  texto: ['=', '<>', 'contem', 'comeca_com', 'em_lista', 'is_null', 'nao_is_null'],
  numero: ['=', '<>', '>', '<', '>=', '<=', 'entre', 'is_null', 'nao_is_null'],
  data: ['data_igual', 'data_maior', 'data_menor', 'data_entre', 'ultimos_n_dias', 'is_null', 'nao_is_null'],
}

/** Rótulos em PT-BR pros operadores — exibidos no <select>. */
export const ROTULO_OPERADOR: Record<Operador, string> = {
  '=': 'igual a',
  '<>': 'diferente de',
  'contem': 'contém',
  'comeca_com': 'começa com',
  'em_lista': 'está em (lista)',
  'is_null': 'está vazio',
  'nao_is_null': 'não está vazio',
  '>': 'maior que',
  '<': 'menor que',
  '>=': 'maior ou igual a',
  '<=': 'menor ou igual a',
  'entre': 'entre',
  'data_igual': 'na data',
  'data_maior': 'após',
  'data_menor': 'antes de',
  'data_entre': 'entre as datas',
  'ultimos_n_dias': 'nos últimos N dias',
}

export type FiltroCampo = {
  coluna: string
  operador: Operador
  valor: string | number | Array<string | number> | null
}

export type FiltrosLivrePayload = {
  tabela: string
  colunas: string[]
  campo_data: string | null
  data_inicio: string | null
  data_fim: string | null
  max_linhas: number | null
  filtros_extra: FiltroCampo[]
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
