import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
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
        <p className="text-slate-500">Carregando...</p>
      </AdminLayout>
    )
  }

  if (erro || !usuario) {
    return (
      <AdminLayout titulo="Editar usuário" voltarPara="/admin/usuarios" rotuloVoltar="Usuários">
        <div className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3">
          {erro ?? 'Usuário não encontrado.'}
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
        <SecaoDados
          usuario={usuario}
          souEu={souEu}
          onSalvo={recarregar}
        />
        {!usuario.is_admin && (
          <SecaoPermissoes
            usuario={usuario}
            relatoriosDisponiveis={relatoriosDisponiveis}
            permissoesIniciais={permissoes}
            onSalvo={recarregar}
          />
        )}
        {usuario.is_admin && (
          <div className="bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl p-4 text-sm text-indigo-800 dark:text-indigo-200">
            Administradores veem todos os relatórios automaticamente. As
            permissões por relatório só se aplicam a usuários comuns.
          </div>
        )}
        <SecaoResetarSenha usuarioId={usuario.id} />
      </div>
    </AdminLayout>
  )
}

// ----------- Seção: Dados -----------

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
    <section className="bg-white dark:bg-slate-900 rounded-xl shadow p-6">
      <h2 className="text-base font-semibold mb-4">Dados</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Username</label>
          <input
            type="text"
            value={usuario.username}
            disabled
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 font-mono text-slate-500"
          />
          <p className="text-xs text-slate-500 mt-1">Username não pode ser alterado.</p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Nome completo</label>
          <input
            type="text"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
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
            <span className="text-xs text-slate-500">(não é possível alterar o próprio)</span>
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
            <span className="text-xs text-slate-500">(não é possível desativar a si mesmo)</span>
          )}
        </label>
      </div>

      {erro && (
        <div className="mt-4 bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3">
          {erro}
        </div>
      )}

      <div className="mt-6">
        <button
          onClick={salvar}
          disabled={salvando}
          className="px-4 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm font-medium disabled:opacity-50"
        >
          {salvando ? 'Salvando...' : 'Salvar dados'}
        </button>
      </div>
    </section>
  )
}

// ----------- Seção: Permissões -----------

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
    <section className="bg-white dark:bg-slate-900 rounded-xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">Permissões por relatório</h2>
        <div className="flex gap-2 text-xs">
          <button
            onClick={marcarTodos}
            className="px-2 py-1 rounded border border-slate-300 dark:border-slate-700"
          >
            Marcar todos
          </button>
          <button
            onClick={limpar}
            className="px-2 py-1 rounded border border-slate-300 dark:border-slate-700"
          >
            Limpar
          </button>
        </div>
      </div>

      {relatoriosDisponiveis.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nenhum relatório cadastrado no sistema.
        </p>
      ) : (
        <div className="space-y-2">
          {relatoriosDisponiveis.map((r) => (
            <label
              key={r.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-700"
            >
              <input
                type="checkbox"
                checked={permissoes.has(r.id)}
                onChange={() => toggle(r.id)}
                className="mt-1 rounded"
              />
              <div>
                <div className="text-sm font-medium">{r.nome}</div>
                <div className="text-xs text-slate-500 font-mono">{r.id}</div>
                <div className="text-xs text-slate-500 mt-1">{r.descricao}</div>
              </div>
            </label>
          ))}
        </div>
      )}

      {erro && (
        <div className="mt-4 bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3">
          {erro}
        </div>
      )}
      {msg && (
        <div className="mt-4 bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm rounded-lg p-3">
          {msg}
        </div>
      )}

      <div className="mt-6">
        <button
          onClick={salvar}
          disabled={salvando}
          className="px-4 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm font-medium disabled:opacity-50"
        >
          {salvando ? 'Salvando...' : 'Salvar permissões'}
        </button>
      </div>
    </section>
  )
}

// ----------- Seção: Resetar Senha -----------

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
    <section className="bg-white dark:bg-slate-900 rounded-xl shadow p-6">
      <h2 className="text-base font-semibold mb-1">Redefinir senha</h2>
      <p className="text-xs text-slate-500 mb-4">
        Encerra todas as sessões ativas deste usuário.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Nova senha</label>
          <input
            type="password"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
          />
          <p className="text-xs text-slate-500 mt-1">Mín. 8 chars + 1 especial.</p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Confirmar</label>
          <input
            type="password"
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
          />
        </div>
      </div>

      {erro && (
        <div className="mt-4 bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3">
          {erro}
        </div>
      )}
      {msg && (
        <div className="mt-4 bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-sm rounded-lg p-3">
          {msg}
        </div>
      )}

      <div className="mt-6">
        <button
          onClick={resetar}
          disabled={enviando || !novaSenha || !confirmacao}
          className="px-4 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm font-medium disabled:opacity-50"
        >
          {enviando ? 'Redefinindo...' : 'Redefinir senha'}
        </button>
      </div>
    </section>
  )
}
