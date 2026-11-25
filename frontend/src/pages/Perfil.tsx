import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  Eye,
  EyeOff,
  KeyRound,
  Save,
  User,
} from 'lucide-react'
import { atualizarPerfil, trocarSenha } from '../api/auth'
import { mensagemErro } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { useToast } from '../lib/toast'
import { cn } from '../lib/utils'

/**
 * Página do próprio usuário — editar nome/email e trocar senha.
 *
 * Divide-se em 2 cards independentes: dados pessoais e trocar senha. Cada
 * um tem seu botão de salvar e estado próprio. Mudanças em um não afetam
 * o outro.
 */
export default function Perfil() {
  const navigate = useNavigate()
  const { usuario, recarregar } = useAuth()

  if (!usuario) return null

  return (
    <div className="mx-auto max-w-2xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/menu')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Menu</span>
      </button>

      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Meu perfil</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Edite seus dados pessoais e troque sua senha. O <code className="font-mono text-xs">username</code>{' '}
          é fixo — pra mudar, fale com um administrador.
        </p>
      </div>

      <DadosPessoaisCard onSalvo={recarregar} />
      <div className="h-6" />
      <TrocarSenhaCard />
    </div>
  )
}

// =============================================================================
// Card 1 — Dados pessoais
// =============================================================================

function DadosPessoaisCard({ onSalvo }: { onSalvo: () => Promise<void> | void }) {
  const { usuario } = useAuth()
  const { toast } = useToast()

  const [nome, setNome] = useState(usuario?.nome_completo ?? '')
  const [email, setEmail] = useState(usuario?.email ?? '')
  const [senhaAtual, setSenhaAtual] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const alterado =
    (usuario && (nome.trim() !== usuario.nome_completo || (email.trim() || null) !== usuario.email)) ?? false

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)

    if (!nome.trim()) return setErro('Informe seu nome completo.')
    if (!senhaAtual) return setErro('Digite sua senha atual pra confirmar.')

    setSalvando(true)
    try {
      await atualizarPerfil({
        nome_completo: nome.trim(),
        email: email.trim() || null,
        senha_atual: senhaAtual,
      })
      toast({ title: 'Perfil atualizado', variant: 'success' })
      setSenhaAtual('')
      await onSalvo()
    } catch (e) {
      const msg = mensagemErro(e, 'Não foi possível salvar.')
      setErro(msg)
      toast({ title: 'Falha ao salvar', description: msg, variant: 'destructive' })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <User className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-base font-semibold">Dados pessoais</h2>
      </div>

      <form onSubmit={submeter} className="space-y-4">
        <Campo label="Usuário">
          <input
            type="text"
            value={usuario?.username ?? ''}
            disabled
            className={cn(campoClasse, 'font-mono bg-muted/40 cursor-not-allowed')}
          />
          <p className="text-xs text-muted-foreground mt-1">Não pode ser alterado.</p>
        </Campo>

        <Campo label="Nome completo">
          <input
            type="text"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            disabled={salvando}
            maxLength={200}
            className={campoClasse}
          />
        </Campo>

        <Campo label="Email" hint="Opcional. Usado pra notificações.">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={salvando}
            placeholder="voce@technocoat.com.br"
            maxLength={200}
            className={campoClasse}
          />
        </Campo>

        <Campo label="Senha atual" hint="Pedimos a senha atual pra confirmar a alteração.">
          <div className="relative">
            <input
              type={mostrarSenha ? 'text' : 'password'}
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              disabled={salvando}
              autoComplete="current-password"
              className={cn(campoClasse, 'pr-10')}
            />
            <button
              type="button"
              onClick={() => setMostrarSenha((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
              aria-label={mostrarSenha ? 'Ocultar' : 'Mostrar'}
            >
              {mostrarSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </Campo>

        {erro && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{erro}</span>
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <Button type="submit" disabled={salvando || !alterado || !senhaAtual}>
            <Save className="h-4 w-4" />
            {salvando ? 'Salvando...' : 'Salvar'}
          </Button>
          {!alterado && (
            <span className="text-xs text-muted-foreground">Sem alterações.</span>
          )}
        </div>
      </form>
    </Card>
  )
}

// =============================================================================
// Card 2 — Trocar senha
// =============================================================================

function TrocarSenhaCard() {
  const { toast } = useToast()
  const [senhaAtual, setSenhaAtual] = useState('')
  const [senhaNova, setSenhaNova] = useState('')
  const [senhaNovaConfirma, setSenhaNovaConfirma] = useState('')
  const [mostrar, setMostrar] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState<string | null>(null)

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setSucesso(null)

    if (!senhaAtual || !senhaNova) {
      return setErro('Preencha os 3 campos.')
    }
    if (senhaNova.length < 8) {
      return setErro('A nova senha deve ter pelo menos 8 caracteres.')
    }
    if (senhaNova !== senhaNovaConfirma) {
      return setErro('As duas digitações da nova senha não conferem.')
    }
    if (senhaNova === senhaAtual) {
      return setErro('A nova senha deve ser diferente da atual.')
    }

    setSalvando(true)
    try {
      const r = await trocarSenha(senhaAtual, senhaNova)
      const msg = r.sessoes_revogadas > 0
        ? `Senha trocada. ${r.sessoes_revogadas} outra${r.sessoes_revogadas > 1 ? 's' : ''} sessão${r.sessoes_revogadas > 1 ? 'ões' : ''} desta conta foi${r.sessoes_revogadas > 1 ? 'ram' : ''} deslogada${r.sessoes_revogadas > 1 ? 's' : ''}.`
        : 'Senha trocada com sucesso.'
      setSucesso(msg)
      toast({ title: 'Senha trocada', description: msg, variant: 'success' })
      setSenhaAtual(''); setSenhaNova(''); setSenhaNovaConfirma('')
    } catch (e) {
      const msg = mensagemErro(e, 'Não foi possível trocar a senha.')
      setErro(msg)
      toast({ title: 'Falha ao trocar senha', description: msg, variant: 'destructive' })
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <KeyRound className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-base font-semibold">Trocar senha</h2>
      </div>

      <form onSubmit={submeter} className="space-y-4">
        <Campo label="Senha atual">
          <CampoSenha
            value={senhaAtual}
            onChange={setSenhaAtual}
            disabled={salvando}
            visivel={mostrar}
            onToggleVisivel={() => setMostrar((v) => !v)}
            autoComplete="current-password"
          />
        </Campo>

        <Campo label="Nova senha" hint="Mínimo 8 caracteres, com pelo menos 1 caractere especial (ex: !@#$%).">
          <CampoSenha
            value={senhaNova}
            onChange={setSenhaNova}
            disabled={salvando}
            visivel={mostrar}
            onToggleVisivel={() => setMostrar((v) => !v)}
            autoComplete="new-password"
          />
        </Campo>

        <Campo label="Confirme a nova senha">
          <CampoSenha
            value={senhaNovaConfirma}
            onChange={setSenhaNovaConfirma}
            disabled={salvando}
            visivel={mostrar}
            onToggleVisivel={() => setMostrar((v) => !v)}
            autoComplete="new-password"
          />
          {senhaNovaConfirma && senhaNova !== senhaNovaConfirma && (
            <p className="text-xs text-destructive mt-1">
              As senhas não conferem.
            </p>
          )}
        </Campo>

        <div className="rounded-md border border-primary/30 bg-primary/5 p-3 text-xs text-muted-foreground">
          <p className="text-foreground font-medium">⚠️ Suas outras sessões vão ser deslogadas</p>
          <p className="mt-1">
            Qualquer login seu em outro navegador ou dispositivo vai cair automaticamente — como
            medida de segurança padrão. Esta sessão atual continua ativa.
          </p>
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

        {sucesso && (
          <div
            role="status"
            className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{sucesso}</span>
          </div>
        )}

        <div className="pt-1">
          <Button type="submit" disabled={salvando}>
            <KeyRound className="h-4 w-4" />
            {salvando ? 'Trocando...' : 'Trocar senha'}
          </Button>
        </div>
      </form>
    </Card>
  )
}

// =============================================================================
// Átomos
// =============================================================================

function Campo({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  )
}

function CampoSenha({
  value,
  onChange,
  disabled,
  visivel,
  onToggleVisivel,
  autoComplete,
}: {
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  visivel: boolean
  onToggleVisivel: () => void
  autoComplete?: string
}) {
  return (
    <div className="relative">
      <input
        type={visivel ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        autoComplete={autoComplete}
        className={cn(campoClasse, 'pr-10')}
      />
      <button
        type="button"
        onClick={onToggleVisivel}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground"
        aria-label={visivel ? 'Ocultar' : 'Mostrar'}
      >
        {visivel ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

const campoClasse =
  'w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50'
