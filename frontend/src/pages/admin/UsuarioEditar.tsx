import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Info } from 'lucide-react'
import { AdminLayout } from './AdminLayout'
import {
  atualizarPermissoes,
  editarUsuario,
  listarUsuarios,
  obterPermissoes,
  resetarSenha,
  UsuarioDetalhe,
} from '../../api/admin'
import { listarRelatorios, RelatorioInfo } from '../../api/relatorios'
import { mensagemErro } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Button } from '../../components/ui/button'
import { Card } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'

export default function UsuarioEditar() {
  const { id } = useParams<{ id: string }>()
  const usuarioId = Number(id)
  const { usuario: me } = useAuth()

  const [usuario, setUsuario] = useState<UsuarioDetalhe | null>(null)
  const [relatoriosDisponiveis, setRelatoriosDisponiveis] = useState<RelatorioInfo[]>([])
  const [permissoes, setPermissoes] = useState<Set<string>>(new Set())
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const recarregar = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [us, rs, p] = await Promise.all([
        listarUsuarios(),
        listarRelatorios(),
        obterPermissoes(usuarioId),
      ])
      const alvo = us.find((u) => u.id === usuarioId) ?? null
      setUsuario(alvo)
      setRelatoriosDisponiveis(rs)
      setPermissoes(new Set(p.relatorios))
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível carregar.'))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    recarregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuarioId])

  if (carregando) {
    return (
      <AdminLayout titulo="Editar usuário" voltarPara="/admin/usuarios" rotuloVoltar="Usuários">
        <p className="text-muted-foreground">Carregando...</p>
      </AdminLayout>
    )
  }

  if (erro || !usuario) {
    return (
      <AdminLayout titulo="Editar usuário" voltarPara="/admin/usuarios" rotuloVoltar="Usuários">
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro ?? 'Usuário não encontrado.'}</span>
        </div>
      </AdminLayout>
    )
  }

  const souEu = me?.id === usuario.id

  return (
    <AdminLayout
      titulo={`Editar: ${usuario.username}`}
      voltarPara="/admin/usuarios"
      rotuloVoltar="Usuários"
    >
      <div className="space-y-6">
        <SecaoDados usuario={usuario} souEu={souEu} onSalvo={recarregar} />
        {!usuario.is_admin && (
          <SecaoPermissoes
            usuario={usuario}
            relatoriosDisponiveis={relatoriosDisponiveis}
            permissoesIniciais={permissoes}
            onSalvo={recarregar}
          />
        )}
        {usuario.is_admin && (
          <Card className="p-4">
            <div className="flex items-start gap-3 text-sm text-foreground">
              <Info className="h-4 w-4 shrink-0 mt-0.5 text-primary" />
              <span>
                Administradores veem todos os relatórios automaticamente. As
                permissões por relatório só se aplicam a usuários comuns.
              </span>
            </div>
          </Card>
        )}
        <SecaoResetarSenha usuarioId={usuario.id} />
      </div>
    </AdminLayout>
  )
}

function SecaoDados({
  usuario,
  souEu,
  onSalvo,
}: {
  usuario: UsuarioDetalhe
  souEu: boolean
  onSalvo: () => void
}) {
  const [nome, setNome] = useState(usuario.nome_completo)
  const [email, setEmail] = useState(usuario.email ?? '')
  const [isAdmin, setIsAdmin] = useState(usuario.is_admin)
  const [ativo, setAtivo] = useState(usuario.ativo)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const salvar = async () => {
    setErro(null)
    setSalvando(true)
    try {
      await editarUsuario(usuario.id, {
        nome_completo: nome,
        email: email.trim() || null,
        is_admin: isAdmin,
        ativo,
      })
      onSalvo()
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível salvar.'))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card className="p-6">
      <h2 className="text-base font-semibold mb-4">Dados</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="e-username">Username</Label>
          <Input id="e-username" value={usuario.username} disabled className="font-mono" />
          <p className="text-xs text-muted-foreground">Username não pode ser alterado.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="e-nome">Nome completo</Label>
          <Input id="e-nome" value={nome} onChange={(e) => setNome(e.target.value)} />
        </div>
        <div className="md:col-span-2 space-y-2">
          <Label htmlFor="e-email">Email</Label>
          <Input
            id="e-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.target.checked)}
            disabled={souEu}
            className="rounded"
          />
          Administrador
          {souEu && (
            <span className="text-xs text-muted-foreground">
              (não é possível alterar o próprio)
            </span>
          )}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={ativo}
            onChange={(e) => setAtivo(e.target.checked)}
            disabled={souEu}
            className="rounded"
          />
          Ativo
          {souEu && (
            <span className="text-xs text-muted-foreground">
              (não é possível desativar a si mesmo)
            </span>
          )}
        </label>
      </div>

      {erro && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}

      <div className="mt-6">
        <Button onClick={salvar} disabled={salvando}>
          {salvando ? 'Salvando...' : 'Salvar dados'}
        </Button>
      </div>
    </Card>
  )
}

function SecaoPermissoes({
  usuario,
  relatoriosDisponiveis,
  permissoesIniciais,
  onSalvo,
}: {
  usuario: UsuarioDetalhe
  relatoriosDisponiveis: RelatorioInfo[]
  permissoesIniciais: Set<string>
  onSalvo: () => void
}) {
  const [permissoes, setPermissoes] = useState<Set<string>>(permissoesIniciais)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const toggle = (id: string) => {
    const nova = new Set(permissoes)
    if (nova.has(id)) nova.delete(id)
    else nova.add(id)
    setPermissoes(nova)
    setMsg(null)
  }

  const marcarTodos = () =>
    setPermissoes(new Set(relatoriosDisponiveis.map((r) => r.id)))
  const limpar = () => setPermissoes(new Set())

  const salvar = async () => {
    setErro(null)
    setMsg(null)
    setSalvando(true)
    try {
      await atualizarPermissoes(usuario.id, Array.from(permissoes))
      setMsg('Permissões atualizadas.')
      onSalvo()
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível salvar as permissões.'))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">Permissões por relatório</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={marcarTodos}>
            Marcar todos
          </Button>
          <Button variant="outline" size="sm" onClick={limpar}>
            Limpar
          </Button>
        </div>
      </div>

      {relatoriosDisponiveis.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum relatório cadastrado no sistema.
        </p>
      ) : (
        <div className="space-y-2">
          {relatoriosDisponiveis.map((r) => (
            <label
              key={r.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-accent/40 transition-colors cursor-pointer"
            >
              <input
                type="checkbox"
                checked={permissoes.has(r.id)}
                onChange={() => toggle(r.id)}
                className="mt-1 rounded"
              />
              <div className="min-w-0">
                <div className="text-sm font-medium">{r.nome}</div>
                <div className="text-xs text-muted-foreground font-mono">{r.id}</div>
                <div className="text-xs text-muted-foreground mt-1">{r.descricao}</div>
              </div>
            </label>
          ))}
        </div>
      )}

      {erro && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}
      {msg && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-success/30 bg-success/10 p-3 text-sm text-success">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{msg}</span>
        </div>
      )}

      <div className="mt-6">
        <Button onClick={salvar} disabled={salvando}>
          {salvando ? 'Salvando...' : 'Salvar permissões'}
        </Button>
      </div>
    </Card>
  )
}

function SecaoResetarSenha({ usuarioId }: { usuarioId: number }) {
  const [novaSenha, setNovaSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const resetar = async () => {
    setErro(null)
    setMsg(null)
    if (novaSenha !== confirmacao) {
      setErro('As senhas não conferem.')
      return
    }
    if (!window.confirm(
      'Isto vai invalidar todas as sessões ativas deste usuário. Continuar?'
    )) return

    setEnviando(true)
    try {
      await resetarSenha(usuarioId, novaSenha)
      setMsg('Senha redefinida. Sessões ativas foram encerradas.')
      setNovaSenha('')
      setConfirmacao('')
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível redefinir a senha.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card className="p-6">
      <h2 className="text-base font-semibold mb-1">Redefinir senha</h2>
      <p className="text-xs text-muted-foreground mb-4">
        Encerra todas as sessões ativas deste usuário.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="r-nova">Nova senha</Label>
          <Input
            id="r-nova"
            type="password"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">Mín. 8 chars + 1 especial.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="r-conf">Confirmar</Label>
          <Input
            id="r-conf"
            type="password"
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
          />
        </div>
      </div>

      {erro && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}
      {msg && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-success/30 bg-success/10 p-3 text-sm text-success">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{msg}</span>
        </div>
      )}

      <div className="mt-6">
        <Button
          onClick={resetar}
          disabled={enviando || !novaSenha || !confirmacao}
        >
          {enviando ? 'Redefinindo...' : 'Redefinir senha'}
        </Button>
      </div>
    </Card>
  )
}
