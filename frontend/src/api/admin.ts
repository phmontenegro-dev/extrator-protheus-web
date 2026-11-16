import { api } from './client'
import type { Usuario } from './auth'

export type UsuarioDetalhe = Usuario

export type UsuarioCreate = {
  username: string
  nome_completo: string
  email?: string | null
  senha: string
  is_admin: boolean
  permissoes: string[]
}

export type UsuarioUpdate = {
  nome_completo?: string
  email?: string | null
  is_admin?: boolean
  ativo?: boolean
}

export type PermissoesResponse = {
  usuario_id: number
  relatorios: string[]
}

export type LogItem = {
  id: number
  timestamp: string
  usuario_id: number | null
  username: string | null
  acao: string
  relatorio_id: string | null
  parametros: Record<string, unknown> | null
  registros_retornados: number | null
  duracao_ms: number | null
  ip_origem: string | null
  sucesso: boolean
  erro_mensagem: string | null
}

export type LogsPagina = {
  itens: LogItem[]
  total: number
  limit: number
  offset: number
}

export type LogsFiltros = {
  username?: string
  acao?: string
  relatorio_id?: string
  desde_dias?: number
  somente_falhas?: boolean
  limit?: number
  offset?: number
}

// ---------- Usuários ----------

export async function listarUsuarios(): Promise<UsuarioDetalhe[]> {
  const resp = await api.get<UsuarioDetalhe[]>('/admin/usuarios')
  return resp.data
}

export async function criarUsuario(payload: UsuarioCreate): Promise<UsuarioDetalhe> {
  const resp = await api.post<UsuarioDetalhe>('/admin/usuarios', payload)
  return resp.data
}

export async function editarUsuario(
  id: number,
  payload: UsuarioUpdate,
): Promise<UsuarioDetalhe> {
  const resp = await api.patch<UsuarioDetalhe>(`/admin/usuarios/${id}`, payload)
  return resp.data
}

export async function resetarSenha(id: number, novaSenha: string): Promise<void> {
  await api.post(`/admin/usuarios/${id}/resetar-senha`, { nova_senha: novaSenha })
}

// ---------- Permissões ----------

export async function obterPermissoes(id: number): Promise<PermissoesResponse> {
  const resp = await api.get<PermissoesResponse>(`/admin/usuarios/${id}/permissoes`)
  return resp.data
}

export async function atualizarPermissoes(
  id: number,
  relatorios: string[],
): Promise<PermissoesResponse> {
  const resp = await api.put<PermissoesResponse>(
    `/admin/usuarios/${id}/permissoes`,
    { relatorios },
  )
  return resp.data
}

// ---------- Logs ----------

export async function listarLogs(filtros: LogsFiltros = {}): Promise<LogsPagina> {
  const resp = await api.get<LogsPagina>('/admin/logs', { params: filtros })
  return resp.data
}
