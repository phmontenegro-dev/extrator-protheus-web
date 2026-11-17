import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

/**
 * Sistema de tema.
 *
 *   "light" / "dark" — força o modo
 *   "system"         — segue o prefers-color-scheme do SO
 *
 * Preferência persiste em localStorage. Aplica/remove a classe `.dark` no
 * <html>, que o Tailwind usa (darkMode: 'class' no config).
 */
type Theme = 'light' | 'dark' | 'system'

type ThemeContextValue = {
  theme: Theme                            // escolha do usuário
  resolvedTheme: 'light' | 'dark'         // o que realmente tá aplicado
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)
const STORAGE_KEY = 'extrator-theme'

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStored(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    // localStorage pode falhar em modo anônimo — ignora.
  }
  return 'system'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStored())
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>(() =>
    theme === 'system' ? getSystemTheme() : theme,
  )

  // Aplica/remove .dark no <html> sempre que resolvedTheme muda.
  useEffect(() => {
    const root = document.documentElement
    if (resolvedTheme === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
  }, [resolvedTheme])

  // Recalcula resolvedTheme quando theme muda ou o sistema muda (em "system").
  useEffect(() => {
    const atualizar = () => {
      setResolvedTheme(theme === 'system' ? getSystemTheme() : theme)
    }
    atualizar()
    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', atualizar)
      return () => mq.removeEventListener('change', atualizar)
    }
  }, [theme])

  const setTheme = (t: Theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch {
      /* ignora */
    }
    setThemeState(t)
  }

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme precisa estar dentro de <ThemeProvider>')
  return ctx
}
