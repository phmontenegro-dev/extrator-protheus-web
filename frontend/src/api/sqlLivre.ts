import { api } from './client'

export type SqlExecutarResponse = {
  colunas: string[]
  linhas: (string | number | null)[][]
  total: number
  truncado: boolean
  duracao_ms: number
}

export async function executarSql(
  sql: string,
  limitePreview = 500,
): Promise<SqlExecutarResponse> {
  const resp = await api.post<SqlExecutarResponse>(
    '/sql-livre/executar',
    { sql, limite_preview: limitePreview },
    { timeout: 5 * 60 * 1000 },  // 5min — cobre o timeout de 240s do backend com folga
  )
  return resp.data
}

/**
 * Baixa o CSV completo (sem limite de linhas, só o timeout do Oracle).
 * Dispara o download via <a download> no navegador.
 */
export async function downloadCsvSql(sql: string, nomeArquivo?: string): Promise<void> {
  const resp = await api.post(
    '/sql-livre/download',
    { sql, nome_arquivo: nomeArquivo || 'consulta_sql.csv' },
    {
      responseType: 'blob',
      timeout: 5 * 60 * 1000,
    },
  )

  const nome = extrairNomeArquivo(
    resp.headers['content-disposition'] as string | undefined,
    nomeArquivo || 'consulta_sql.csv',
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
