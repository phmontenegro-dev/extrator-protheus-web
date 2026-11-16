import { FormEvent, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { mensagemErro } from '../api/client'

export default function Login() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !senha) {
      setErro('Preencha usuário e senha.')
      return
    }
    setErro(null)
    setEnviando(true)
    try {
      await login(username.trim(), senha)
      // AuthProvider seta o usuário; o <RedirectIfAuth> em /login detecta
      // e redireciona para /menu (ou rota original).
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível entrar.'))
      setSenha('')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold mb-1">Extrator Protheus</h1>
        <p className="text-slate-500 dark:text-slate-400 mb-6 text-sm">
          Acesse com suas credenciais.
        </p>

        <form onSubmit={submeter} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium mb-1">
              Usuário
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={enviando}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
            />
          </div>

          <div>
            <label htmlFor="senha" className="block text-sm font-medium mb-1">
              Senha
            </label>
            <input
              id="senha"
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              disabled={enviando}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
            />
          </div>

          {erro && (
            <div
              role="alert"
              className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3"
            >
              {erro}
            </div>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="w-full bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-lg py-2 font-medium disabled:opacity-50"
          >
            {enviando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
