import { useEffect, useMemo, useState } from 'react'
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
  TerminalSquare,
  Timer,
  Truck,
} from 'lucide-react'
import { listarRelatorios, RelatorioInfo } from '../api/relatorios'
import { mensagemErro } from '../api/client'
import { Card, CardContent } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'

/** Mapa opcional id → ícone. Padrão é FileSpreadsheet. */
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
  paradas_maquina: Timer,
  relatorio_livre: Sparkles,
  codigo_sql: TerminalSquare,
}

/**
 * Pra onde navegar quando o usuário clica num card. A maioria vai pra
 * /relatorios/<id>, mas tipos especiais (livre e sql) têm rotas próprias.
 */
function rotaDoRelatorio(r: RelatorioInfo): string {
  if (r.filtros === 'sql') return '/sql'
  return `/relatorios/${r.id}`
}

type Grupo = {
  chave: string                        // "area:<id>" ou "outros"
  nome: string                         // "Contábil" | "Outros"
  ordem: number                        // pra ordenar; "outros" vai ser grande
  relatorios: RelatorioInfo[]
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

  /**
   * Agrupa por área. Mantém relatórios ordenados por nome dentro do grupo.
   * Grupos ordenados por `area_ordem` (menor primeiro). "Outros" vai no fim.
   */
  const grupos: Grupo[] = useMemo(() => {
    const map = new Map<string, Grupo>()
    for (const r of relatorios) {
      let chave: string, nome: string, ordem: number
      if (r.area_id == null) {
        chave = 'outros'
        nome = 'Outros'
        ordem = Number.MAX_SAFE_INTEGER
      } else {
        chave = `area:${r.area_id}`
        nome = r.area_nome ?? '(sem nome)'
        ordem = r.area_ordem ?? 0
      }
      let g = map.get(chave)
      if (!g) {
        g = { chave, nome, ordem, relatorios: [] }
        map.set(chave, g)
      }
      g.relatorios.push(r)
    }
    const lista = Array.from(map.values())
    // Ordena grupos; dentro de cada, ordena relatórios por nome
    lista.sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome, 'pt-BR'))
    for (const g of lista) {
      g.relatorios.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
    }
    return lista
  }, [relatorios])

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
            <Card key={i} className="p-5">
              <div className="flex items-start gap-3">
                <Skeleton className="h-10 w-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-5/6" />
                </div>
              </div>
            </Card>
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

      {!carregando && !erro && grupos.map((g) => (
        <section key={g.chave} className="mb-8 last:mb-0">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 border-b border-border pb-1.5">
            {g.nome}
            <span className="ml-2 text-[10px] font-normal lowercase tracking-normal opacity-70">
              ({g.relatorios.length} {g.relatorios.length === 1 ? 'relatório' : 'relatórios'})
            </span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {g.relatorios.map((r) => {
              const Icone = ICONES[r.id] ?? FileSpreadsheet
              const destaque = r.filtros === 'livre' || r.filtros === 'sql'
              return (
                <button
                  key={r.id}
                  onClick={() => navigate(rotaDoRelatorio(r))}
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
        </section>
      ))}
    </div>
  )
}
