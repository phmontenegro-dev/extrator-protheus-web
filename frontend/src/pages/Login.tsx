import { FormEvent, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { mensagemErro } from '../api/client'
import { Logo } from '../components/Logo'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { ThemeToggle } from '../components/ThemeToggle'

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
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível entrar.'))
      setSenha('')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      {/* Theme toggle discreto no canto */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-8">
          <Logo className="scale-150" />
        </div>

        <Card>
          <CardHeader className="space-y-1 text-center">
            <h1 className="text-xl font-semibold">Entrar</h1>
            <p className="text-sm text-muted-foreground">
              Acesse com suas credenciais
            </p>
          </CardHeader>

          <CardContent>
            <form onSubmit={submeter} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Usuário</Label>
                <Input
                  id="username"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={enviando}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="senha">Senha</Label>
                <Input
                  id="senha"
                  type="password"
                  autoComplete="current-password"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  disabled={enviando}
                />
              </div>

              {erro && (
                <div
                  role="alert"
                  className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{erro}</span>
                </div>
              )}

              <Button type="submit" disabled={enviando} className="w-full">
                {enviando ? 'Entrando...' : 'Entrar'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Extrator Protheus · Technocoat
        </p>
      </div>
    </div>
  )
}
