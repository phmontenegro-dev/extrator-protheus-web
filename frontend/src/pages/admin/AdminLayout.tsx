import { ReactNode } from 'react'
import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

/**
 * Container padrão das páginas admin. Agora o sidebar global já cuida do
 * menu/logout/tema — aqui só exibimos título + botão voltar opcional.
 */
export function AdminLayout({
  titulo,
  voltarPara,
  rotuloVoltar,
  children,
}: {
  titulo: string
  voltarPara?: string
  rotuloVoltar?: string
  children: ReactNode
}) {
  const navigate = useNavigate()
  return (
    <div className="mx-auto max-w-5xl px-6 py-8 md:py-10">
      <div className="mb-6 flex items-center gap-3">
        {voltarPara !== undefined && (
          <button
            onClick={() => navigate(voltarPara)}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            <span>{rotuloVoltar ?? 'Voltar'}</span>
          </button>
        )}
      </div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">{titulo}</h1>
      </div>
      {children}
    </div>
  )
}
