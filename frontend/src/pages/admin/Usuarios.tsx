import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, Plus, X } from 'lucide-react'
import { AdminLayout } from './AdminLayout'
import { criarUsuario, listarUsuarios, UsuarioDetalhe } from '../../api/admin'
import { listarRelatorios, RelatorioInfo } from '../../api/relatorios'
import { mensagemErro } from '../../api/client'
import { Button } from '../../components/ui/button'
import { Card } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Skeleton } from '../../components/ui/skeleton'
import { useToast } from '../../lib/toast'

export default function Usuarios() {
  const navigate = useNavigate()
  const [usuarios, setUsuarios] = useState<UsuarioDetalhe[]>([])
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modalAberta, setModalAberta] = useState(false)

  const recarregar = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [us, rs] = await Promise.all([listarUsuarios(), listarRelatorios()])
      setUsuarios(us)
      setRelatorios(rs)
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível carregar.'))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    recarregar()
  }, [])

  return (
    <AdminLayout titulo="Usuários" voltarPara="/admin" rotuloVoltar="Painel">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {usuarios.length} {usuarios.length === 1 ? 'usuário' : 'usuários'}
        </p>
        <Button onClick={() => setModalAberta(true)}>
          <Plus className="h-4 w-4" />
          Novo usuário
        </Button>
      </div>

      {carregando && (
        <Card className="overflow-hidden">
          <div className="p-4 space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        </Card>
      )}

      {erro && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive mb-4"
        >
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}

      {!carregando && !erro && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Usuário</th>
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Admin</th>
                <th className="px-4 py-3">Ativo</th>
                <th className="px-4 py-3">Último login</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id} className="border-t border-border">
                  <td className="px-4 py-3 font-mono">{u.username}</td>
                  <td className="px-4 py-3">{u.nome_completo}</td>
                  <td className="px-4 py-3">
                    {u.is_admin ? (
                      <span className="px-2 py-0.5 rounded bg-primary/15 text-primary text-xs font-semibold">
                        admin
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {u.ativo ? (
                      <span className="text-success">Ativo</span>
                    ) : (
                      <span className="text-muted-foreground">Inativo</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {u.ultimo_login
                      ? new Date(u.ultimo_login).toLocaleString('pt-BR')
                      : 'nunca'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => navigate(`/admin/usuarios/${u.id}`)}
                      className="text-sm text-primary hover:underline"
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {modalAberta && (
        <ModalNovoUsuario
          relatoriosDisponiveis={relatorios}
          onFechar={() => setModalAberta(false)}
          onCriado={async () => {
            setModalAberta(false)
            await recarregar()
          }}
        />
      )}
    </AdminLayout>
  )
}

function ModalNovoUsuario({
  relatoriosDisponiveis,
  onFechar,
  onCriado,
}: {
  relatoriosDisponiveis: RelatorioInfo[]
  onFechar: () => void
  onCriado: () => void
}) {
  const { toast } = useToast()
  const [username, setUsername] = useState('')
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const [permissoes, setPermissoes] = useState<Set<string>>(new Set())
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const togglePerm = (id: string) => {
    const nova = new Set(permissoes)
    if (nova.has(id)) nova.delete(id)
    else nova.add(id)
    setPermissoes(nova)
  }

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const usernameLimpo = username.trim().toLowerCase()
      await criarUsuario({
        username: usernameLimpo,
        nome_completo: nome.trim(),
        email: email.trim() || null,
        senha,
        is_admin: isAdmin,
        permissoes: isAdmin ? [] : Array.from(permissoes),
      })
      toast({
        title: 'Usuário criado',
        description: `@${usernameLimpo} está pronto pra logar.`,
        variant: 'success',
      })
      onCriado()
    } catch (e) {
      // Erro fica no modal (visível junto do form) em vez de toast —
      // o usuário acabou de digitar e pode querer corrigir ali mesmo.
      setErro(mensagemErro(e, 'Não foi possível criar o usuário.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onClick={onFechar}
    >
      <Card
        className="w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Novo usuário</h2>
          <button
            onClick={onFechar}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submeter} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="n-username">Username</Label>
            <Input
              id="n-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="n-nome">Nome completo</Label>
            <Input
              id="n-nome"
              type="text"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="n-email">
              Email <span className="text-muted-foreground text-xs">(opcional)</span>
            </Label>
            <Input
              id="n-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="n-senha">
              Senha{' '}
              <span className="text-muted-foreground text-xs">
                (mín. 8 chars + 1 especial)
              </span>
            </Label>
            <Input
              id="n-senha"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
          </div>

          <label className="flex items-center gap-2 text-sm pt-2">
            <input
              type="checkbox"
              checked={isAdmin}
              onChange={(e) => setIsAdmin(e.target.checked)}
              className="rounded"
            />
            Administrador (vê tudo, sem precisar de permissões)
          </label>

          {!isAdmin && (
            <div>
              <div className="text-sm font-medium mb-2">Permissões por relatório</div>
              {relatoriosDisponiveis.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Nenhum relatório cadastrado no sistema.
                </p>
              ) : (
                <div className="space-y-1 border border-border rounded-lg p-3 max-h-40 overflow-y-auto">
                  {relatoriosDisponiveis.map((r) => (
                    <label key={r.id} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={permissoes.has(r.id)}
                        onChange={() => togglePerm(r.id)}
                        className="mt-1 rounded"
                      />
                      <span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {r.id}
                        </span>{' '}
                        — {r.nome}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {erro && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{erro}</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onFechar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? 'Criando...' : 'Criar'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
