import { api } from './client'

/**
 * Representação pública do usuário, igual ao UsuarioOut do backend.
 * Campos nunca incluem senha nem hash.
 */
export type Usuario = {
  id: number
  username: string
  nome_completo: string
  email: string | null
  is_admin: boolean
  ativo: boolean
  criado_em: string
  ultimo_login: string | null
}

export type LoginResponse = {
  ok: boolean
  usuario: Usuario
}

export async function login(username: string, senha: string): Promise<Usuario> {
  const resp = await api.post<LoginResponse>('/auth/login', { username, senha })
  return resp.data.usuario
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

/**
 * Retorna o usuário autenticado ou null se não há sessão.
 * Usado no bootstrap da aplicação para decidir se mostra login ou menu.
 */
export async function me(): Promise<Usuario | null> {
  try {
    const resp = await api.get<Usuario>('/auth/me')
    return resp.data
  } catch {
    // Qualquer erro aqui (401, timeout, offline) significa "não logado"
    // para efeito de bootstrap. O interceptor global já cuida de redirect
    // em 401 durante o uso normal.
    return null
  }
}

// ---- Perfil do próprio usuário (Etapa 17) ----

export type AtualizarPerfilPayload = {
  nome_completo: string
  email: string | null
  senha_atual: string
}

export async function atualizarPerfil(p: AtualizarPerfilPayload): Promise<Usuario> {
  const resp = await api.patch<Usuario>('/auth/me', p)
  return resp.data
}

export type TrocarSenhaResponse = {
  ok: boolean
  sessoes_revogadas: number
}

export async function trocarSenha(
  senha_atual: string,
  senha_nova: string,
): Promise<TrocarSenhaResponse> {
  const resp = await api.post<TrocarSenhaResponse>('/auth/me/trocar-senha', {
    senha_atual,
    senha_nova,
  })
  return resp.data
}
