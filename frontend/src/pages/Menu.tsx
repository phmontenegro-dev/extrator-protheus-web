import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Beaker,
  Boxes,
  FileSpreadsheet,
  Package,
  Receipt,
  ScrollText,
  Sparkles,
  Truck,
} from 'lucide-react'
import { listarRelatorios, RelatorioInfo } from '../api/relatorios'
import { mensagemErro } from '../api/client'
import { Card, CardContent } from '../components/ui/card'
import { cn } from '../lib/utils'

/**
 * Mapa opcional id → ícone. Um relatório sem entrada aqui ganha o ícone
 * padrão FileSpreadsheet.
 */
const ICONES: Record<string, typeof FileSpreadsheet> = {
  ct2010: ScrollText,
  qpr010: Beaker,
  sft010: Receipt,
  sd3010: Boxes,
  sb8_suzano: Package,
  sd1_suzano: Truck,
  sd2_suzano: Truck,
  sd4_suzano: Package,
  sh6_suzano: BarChart3,
  consolidado_suzano_jhon: BarChart3,
  relatorio_livre: Sparkles,
}

export default function Menu() {
  const navigate = useNavigate()
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    listarRelatorios()
      .then(setRelatorios)
      .catch((e) =>
        setErro(mensagemErro(e, 'Não foi possível carregar os relatórios.')),
      )
      .finally(() => setCarregando(false))
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 md:py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Relatórios disponíveis</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Selecione um relatório para configurar os filtros e extrair.
        </p>
      </div>

      {carregando && (
        <div className="grid gap-4 md:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="h-28 animate-pulse" />
          ))}
        </div>
      )}

      {erro && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {erro}
        </div>
      )}

      {!carregando && !erro && relatorios.length === 0 && (
        <Card className="p-8 text-center text-muted-foreground">
          Nenhum relatório disponível. Fale com o administrador.
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {relatorios.map((r) => {
          const Icone = ICONES[r.id] ?? FileSpreadsheet
          const destaque = r.filtros === 'livre'
          return (
            <button
              key={r.id}
              onClick={() => navigate(`/relatorios/${r.id}`)}
              className="text-left"
            >
              <Card
                className={cn(
                  'h-full transition-all hover:shadow-md hover:border-primary/40',
                  destaque && 'border-primary/40 bg-primary/5',
                )}
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                        destaque
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-accent text-accent-foreground',
                      )}
                    >
                      <Icone className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold truncate">{r.nome}</div>
                      <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {r.descricao}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </button>
          )
        })}
      </div>
    </div>
  )
}
