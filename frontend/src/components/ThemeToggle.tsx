import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

/**
 * Toggle de tema — 3 opções em botões lado a lado.
 * Compacto o bastante pra encaixar no footer do sidebar.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const opcoes: {
    valor: 'light' | 'dark' | 'system'
    icone: typeof Sun
    label: string
  }[] = [
    { valor: 'light', icone: Sun, label: 'Claro' },
    { valor: 'dark', icone: Moon, label: 'Escuro' },
    { valor: 'system', icone: Monitor, label: 'Sistema' },
  ]

  return (
    <div
      role="group"
      aria-label="Tema"
      className="inline-flex items-center rounded-md border border-border bg-muted p-0.5"
    >
      {opcoes.map(({ valor, icone: Icone, label }) => (
        <button
          key={valor}
          type="button"
          aria-label={label}
          title={label}
          onClick={() => setTheme(valor)}
          className={cn(
            'flex h-7 w-8 items-center justify-center rounded transition-colors',
            theme === valor
              ? 'bg-surface text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icone className="h-4 w-4" />
        </button>
      ))}
    </div>
  )
}
