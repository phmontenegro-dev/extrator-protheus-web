import { useNavigate } from 'react-router-dom'
import { AdminLayout } from './AdminLayout'

export default function Admin() {
  const navigate = useNavigate()

  const cards = [
    {
      id: 'usuarios',
      titulo: 'Usuários',
      descricao: 'Criar, editar, desativar usuários e definir permissões por relatório.',
      rota: '/admin/usuarios',
    },
    {
      id: 'logs',
      titulo: 'Logs de acesso',
      descricao: 'Auditoria de login, logout, extrações e ações administrativas.',
      rota: '/admin/logs',
    },
  ]

  return (
    <AdminLayout titulo="Painel administrativo" voltarPara="/menu" rotuloVoltar="Menu">
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map((c) => (
          <button
            key={c.id}
            onClick={() => navigate(c.rota)}
            className="text-left bg-white dark:bg-slate-900 rounded-xl shadow p-5 hover:shadow-md transition border border-transparent hover:border-slate-300 dark:hover:border-slate-700"
          >
            <div className="font-semibold mb-1">{c.titulo}</div>
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {c.descricao}
            </div>
          </button>
        ))}
      </div>
    </AdminLayout>
  )
}
