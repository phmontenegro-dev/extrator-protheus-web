import { useNavigate } from 'react-router-dom'
import { ScrollText, Users } from 'lucide-react'
import { AdminLayout } from './AdminLayout'
import { Card, CardContent } from '../../components/ui/card'

export default function Admin() {
  const navigate = useNavigate()

  const cards = [
    {
      id: 'usuarios',
      icone: Users,
      titulo: 'Usuários',
      descricao: 'Criar, editar, desativar usuários e definir permissões por relatório.',
      rota: '/admin/usuarios',
    },
    {
      id: 'logs',
      icone: ScrollText,
      titulo: 'Logs de acesso',
      descricao: 'Auditoria de login, logout, extrações e ações administrativas.',
      rota: '/admin/logs',
    },
  ]

  return (
    <AdminLayout titulo="Painel administrativo" voltarPara="/menu" rotuloVoltar="Menu">
      <div className="grid gap-4 md:grid-cols-2">
        {cards.map((c) => {
          const Icone = c.icone
          return (
            <button
              key={c.id}
              onClick={() => navigate(c.rota)}
              className="text-left"
            >
              <Card className="h-full transition-all hover:shadow-md hover:border-primary/40">
                <CardContent className="p-5">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                      <Icone className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold">{c.titulo}</div>
                      <div className="text-sm text-muted-foreground mt-1">
                        {c.descricao}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </button>
          )
        })}
      </div>
    </AdminLayout>
  )
}

