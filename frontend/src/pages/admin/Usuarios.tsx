import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AdminLayout } from './AdminLayout'
import { criarUsuario, listarUsuarios, UsuarioDetalhe } from '../../api/admin'
import { listarRelatorios, RelatorioInfo } from '../../api/relatorios'
import { mensagemErro } from '../../api/client'

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
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {usuarios.length} {usuarios.length === 1 ? 'usuário' : 'usuários'}
        </p>
        <button
          onClick={() => setModalAberta(true)}
          className="bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-lg px-4 py-2 text-sm font-medium"
        >
          + Novo usuário
        </button>
      </div>

      {carregando && <p className="text-slate-500">Carregando...</p>}

      {erro && (
        <div
          role="alert"
          className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3 mb-4"
        >
          {erro}
        </div>
      )}

      {!carregando && !erro && (
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800 text-left text-xs uppercase text-slate-500 dark:text-slate-400">
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
                <tr
                  key={u.id}
                  className="border-t border-slate-100 dark:border-slate-800"
                >
                  <td className="px-4 py-3 font-mono">{u.username}</td>
                  <td className="px-4 py-3">{u.nome_completo}</td>
                  <td className="px-4 py-3">
                    {u.is_admin ? (
                      <span className="px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-xs font-semibold">
                        admin
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {u.ativo ? (
                      <span className="text-emerald-600 dark:text-emerald-400">Ativo</span>
                    ) : (
                      <span className="text-slate-400">Inativo</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {u.ultimo_login
                      ? new Date(u.ultimo_login).toLocaleString('pt-BR')
                      : 'nunca'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => navigate(`/admin/usuarios/${u.id}`)}
                      className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
      await criarUsuario({
        username: username.trim().toLowerCase(),
        nome_completo: nome.trim(),
        email: email.trim() || null,
        senha,
        is_admin: isAdmin,
        permissoes: isAdmin ? [] : Array.from(permissoes),
      })
      onCriado()
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível criar o usuário.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50"
      onClick={onFechar}
    >
      <div
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold mb-4">Novo usuário</h2>
        <form onSubmit={submeter} className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Nome completo</label>
            <input
              type="text"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Email <span className="text-slate-400 text-xs">(opcional)</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Senha{' '}
              <span className="text-slate-400 text-xs">
                (mín. 8 chars + 1 especial)
              </span>
            </label>
            <input
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
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
              <div className="text-sm font-medium mb-2">
                Permissões por relatório
              </div>
              {relatoriosDisponiveis.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Nenhum relatório cadastrado no sistema.
                </p>
              ) : (
                <div className="space-y-1 border border-slate-200 dark:border-slate-700 rounded-lg p-3 max-h-40 overflow-y-auto">
                  {relatoriosDisponiveis.map((r) => (
                    <label key={r.id} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={permissoes.has(r.id)}
                        onChange={() => togglePerm(r.id)}
                        className="mt-1 rounded"
                      />
                      <span>
                        <span className="font-mono text-xs text-slate-500">
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
            <div className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3">
              {erro}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onFechar}
              className="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-700 text-sm"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={enviando}
              className="px-4 py-2 rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm font-medium disabled:opacity-50"
            >
              {enviando ? 'Criando...' : 'Criar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
