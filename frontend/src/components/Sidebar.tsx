import { useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  ChevronRight,
  FileSpreadsheet,
  FolderTree,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Wand2,
  Users,
  X,
} from 'lucide-react'

import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'
import { Button } from './ui/button'
import { useAuth } from '@/auth/AuthContext'
import { listarRelatorios, RelatorioInfo } from '@/api/relatorios'
import { cn } from '@/lib/utils'

/**
 * Sidebar fixa à esquerda em desktop, deslizante em mobile (≤ md).
 *
 * Divisões:
 *   - Relatórios prontos  → cards de cada relatório (filtros != "livre")
 *   - Relatório livre     → separado (ferramenta de exploração)
 *   - Código SQL          → placeholder "em breve" (Etapa 9)
 *   - Admin               → só aparece pra is_admin
 *
 * A lista de relatórios é carregada ao montar; já respeita permissão
 * (backend retorna só os que o usuário pode ver).
 */
export function Sidebar() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [mobileAberto, setMobileAberto] = useState(false)

  useEffect(() => {
    listarRelatorios()
      .then(setRelatorios)
      .catch(() => {
        /* falha silenciosa — o menu principal mostra o erro */
      })
  }, [])

  // Fecha sidebar mobile quando navega.
  useEffect(() => {
    setMobileAberto(false)
  }, [location.pathname])

  /**
   * Separa o relatório livre dos "prontos" (que agrupamos por área).
   * Dentro dos prontos: agrupa por area_id, ordena por area_ordem, "Outros"
   * (sem área) no fim.
   */
  const { prontosGrupos, livres } = useMemo(() => {
    const livres = relatorios.filter((r) => r.filtros === 'livre')
    const prontos = relatorios.filter((r) => r.filtros !== 'livre')

    const mapa = new Map<
      string,
      { chave: string; nome: string; ordem: number; itens: RelatorioInfo[] }
    >()
    for (const r of prontos) {
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
      let g = mapa.get(chave)
      if (!g) {
        g = { chave, nome, ordem, itens: [] }
        mapa.set(chave, g)
      }
      g.itens.push(r)
    }
    const prontosGrupos = Array.from(mapa.values())
    prontosGrupos.sort(
      (a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome, 'pt-BR'),
    )
    for (const g of prontosGrupos) {
      g.itens.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
    }
    return { prontosGrupos, livres }
  }, [relatorios])

  return (
    <>
      {/* Botão mobile pra abrir o sidebar */}
      <button
        aria-label="Abrir menu"
        onClick={() => setMobileAberto(true)}
        className="fixed top-3 left-3 z-40 rounded-md border border-border bg-surface p-2 shadow-sm md:hidden"
      >
        <MenuIcon className="h-5 w-5" />
      </button>

      {/* Overlay mobile */}
      {mobileAberto && (
        <div
          onClick={() => setMobileAberto(false)}
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
        />
      )}

      {/* Sidebar — fixed em desktop, slide-in em mobile */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-surface',
          'transition-transform duration-200 ease-out',
          mobileAberto ? 'translate-x-0' : '-translate-x-full',
          'md:translate-x-0',
        )}
      >
        {/* Header do sidebar */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-border">
          <Logo />
          <button
            onClick={() => setMobileAberto(false)}
            className="rounded p-1 text-muted-foreground hover:text-foreground md:hidden"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Conteúdo scrollável */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {/* RELATÓRIOS PRONTOS, AGRUPADOS POR ÁREA */}
          {prontosGrupos.length === 0 && (
            <Secao
              titulo="Relatórios prontos"
              icone={<FileSpreadsheet className="h-3.5 w-3.5" />}
            >
              <ItemVazio texto="Nenhum disponível" />
            </Secao>
          )}
          {prontosGrupos.map((g) => (
            <Secao
              key={g.chave}
              titulo={g.nome}
              icone={<FolderTree className="h-3.5 w-3.5" />}
            >
              {g.itens.map((r) => (
                <ItemNav
                  key={r.id}
                  to={`/relatorios/${r.id}`}
                  label={r.nome}
                  compact
                />
              ))}
            </Secao>
          ))}

          {/* RELATÓRIO LIVRE */}
          <Secao titulo="Relatório livre" icone={<Wand2 className="h-3.5 w-3.5" />}>
            {livres.length === 0 && <ItemVazio texto="Sem permissão" />}
            {livres.map((r) => (
              <ItemNav
                key={r.id}
                to={`/relatorios/${r.id}`}
                label="Extração livre"
                icon={<Sparkles className="h-4 w-4" />}
              />
            ))}
          </Secao>

          {/* CÓDIGO SQL — placeholder (Etapa 9) */}
          <Secao titulo="Avançado" icone={<TerminalSquare className="h-3.5 w-3.5" />}>
            <div className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground cursor-not-allowed">
              <TerminalSquare className="h-4 w-4" />
              <span className="flex-1">Código SQL</span>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wider">
                em breve
              </span>
            </div>
          </Secao>

          {/* ADMIN — só pra admin */}
          {usuario?.is_admin && (
            <Secao
              titulo="Administração"
              icone={<ShieldCheck className="h-3.5 w-3.5" />}
            >
              <ItemNav
                to="/admin"
                label="Painel"
                icon={<LayoutDashboard className="h-4 w-4" />}
                exact
              />
              <ItemNav
                to="/admin/usuarios"
                label="Usuários"
                icon={<Users className="h-4 w-4" />}
              />
              <ItemNav
                to="/admin/areas"
                label="Áreas"
                icon={<FolderTree className="h-4 w-4" />}
              />
              <ItemNav
                to="/admin/logs"
                label="Logs de acesso"
                icon={<ScrollText className="h-4 w-4" />}
              />
            </Secao>
          )}
        </nav>

        {/* Footer: usuário + tema + sair */}
        <div className="border-t border-border p-3 space-y-3">
          <button
            onClick={() => navigate('/menu')}
            className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-accent"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground font-semibold text-xs">
              {(usuario?.nome_completo ?? '?')
                .split(' ')
                .map((p) => p[0])
                .slice(0, 2)
                .join('')
                .toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{usuario?.nome_completo}</div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="truncate">@{usuario?.username}</span>
                {usuario?.is_admin && (
                  <span className="rounded bg-primary/15 px-1 py-0.5 text-[9px] font-semibold uppercase text-primary">
                    admin
                  </span>
                )}
              </div>
            </div>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </button>
          <div className="flex items-center justify-between">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              className="text-muted-foreground"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>
    </>
  )
}

// ---- componentes auxiliares ----

function Secao({
  titulo,
  icone,
  children,
}: {
  titulo: string
  icone: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {icone}
        <span>{titulo}</span>
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  )
}

function ItemNav({
  to,
  label,
  icon,
  exact,
  compact,
}: {
  to: string
  label: string
  icon?: React.ReactNode
  exact?: boolean
  compact?: boolean
}) {
  return (
    <NavLink
      to={to}
      end={exact}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors',
          'hover:bg-accent hover:text-accent-foreground',
          isActive
            ? 'bg-accent text-accent-foreground font-medium'
            : 'text-foreground/80',
          compact && 'text-[13px] py-1',
        )
      }
    >
      {icon ?? (
        <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
      )}
      <span className="flex-1 truncate">{label}</span>
    </NavLink>
  )
}

function ItemVazio({ texto }: { texto: string }) {
  return (
    <div className="px-3 py-1.5 text-xs text-muted-foreground italic">
      {texto}
    </div>
  )
}
