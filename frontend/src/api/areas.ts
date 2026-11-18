import { api } from './client'

export type Area = {
  id: number
  nome: string
  descricao: string | null
  ordem: number
  criado_em: string
}

export type AreaCreate = {
  nome: string
  descricao?: string | null
  ordem?: number
}

export type AreaUpdate = {
  nome?: string
  descricao?: string | null
  ordem?: number
}

export type RelatorioAreaInfo = {
  relatorio_id: string
  area_id: number | null
}

export async function listarAreas(): Promise<Area[]> {
  const resp = await api.get<Area[]>('/admin/areas')
  return resp.data
}

export async function criarArea(payload: AreaCreate): Promise<Area> {
  const resp = await api.post<Area>('/admin/areas', payload)
  return resp.data
}

export async function editarArea(id: number, payload: AreaUpdate): Promise<Area> {
  const resp = await api.patch<Area>(`/admin/areas/${id}`, payload)
  return resp.data
}

export async function removerArea(id: number): Promise<void> {
  await api.delete(`/admin/areas/${id}`)
}

export async function reordenarAreas(ids: number[]): Promise<Area[]> {
  const resp = await api.put<Area[]>('/admin/areas/ordem', { ids })
  return resp.data
}

export async function listarAtribuicoes(): Promise<RelatorioAreaInfo[]> {
  const resp = await api.get<RelatorioAreaInfo[]>('/admin/relatorio-areas')
  return resp.data
}

export async function atribuirRelatorio(
  relatorioId: string,
  areaId: number | null,
): Promise<RelatorioAreaInfo> {
  const resp = await api.put<RelatorioAreaInfo>(
    `/admin/relatorio-areas/${encodeURIComponent(relatorioId)}`,
    { area_id: areaId },
  )
  return resp.data
}
