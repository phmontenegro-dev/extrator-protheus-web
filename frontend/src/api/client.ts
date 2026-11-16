import axios, { AxiosError } from 'axios'

/**
 * Cliente axios usado por toda a aplicação.
 *
 * baseURL = '/api' casa com o proxy do Vite (ver vite.config.ts), que em dev
 * encaminha para http://localhost:8000. Em produção, o FastAPI serve o build
 * estático e expõe os mesmos caminhos — então nada muda.
 *
 * withCredentials: true é essencial para que o cookie httpOnly de sessão
 * seja enviado em todas as requisições autenticadas.
 */
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 60_000,
})

/**
 * Interceptor global: quando QUALQUER request autenticado retorna 401
 * (sessão expirada / revogada / usuário desativado), joga o usuário pra
 * tela de login imediatamente.
 *
 * O endpoint de login em si retorna 401 em caso de senha errada — por isso
 * ignoramos o redirect quando a request foi para /auth/login (tratamento
 * fica na tela de login).
 */
api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    const status = error.response?.status
    const url = error.config?.url ?? ''
    const ehLogin = url.endsWith('/auth/login')
    if (status === 401 && !ehLogin) {
      // location.assign em vez de react-router aqui porque este arquivo
      // não faz parte do grafo de componentes React.
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

/** Mensagem de erro amigável a partir de uma resposta da API. */
export function mensagemErro(e: unknown, fallback = 'Erro inesperado.'): string {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (e.message) return e.message
  }
  if (e instanceof Error) return e.message
  return fallback
}
