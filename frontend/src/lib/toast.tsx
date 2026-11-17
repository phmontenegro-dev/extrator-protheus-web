import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { cn } from './utils'

/**
 * Sistema de toasts (notificações pop-up).
 *
 * Uso:
 *   const toast = useToast()
 *   toast({ title: 'Salvo!', variant: 'success' })
 *   toast({ title: 'Erro', description: 'Detalhe', variant: 'destructive' })
 *
 * Variantes: default (info), success, destructive.
 * Auto-close em 4s (ou configurável via duration).
 */

type ToastVariant = 'default' | 'success' | 'destructive'

export type ToastOptions = {
  title: string
  description?: string
  variant?: ToastVariant
  duration?: number       // ms; default 4000
}

type ToastItem = ToastOptions & { id: number }

type ToastContextValue = {
  toast: (opts: ToastOptions) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

let idSeq = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setItems((xs) => xs.filter((x) => x.id !== id))
  }, [])

  const toast = useCallback(
    (opts: ToastOptions) => {
      const id = ++idSeq
      setItems((xs) => [...xs, { ...opts, id }])
    },
    [],
  )

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      <Toaster items={items} dismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast precisa estar dentro de <ToastProvider>')
  return ctx
}

// ---- componentes visuais ----

function Toaster({
  items,
  dismiss,
}: {
  items: ToastItem[]
  dismiss: (id: number) => void
}) {
  return (
    <div
      className="fixed top-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2 pointer-events-none"
      role="region"
      aria-label="Notificações"
    >
      {items.map((t) => (
        <Toast key={t.id} item={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  )
}

function Toast({
  item,
  onDismiss,
}: {
  item: ToastItem
  onDismiss: () => void
}) {
  const duration = item.duration ?? 4000

  // Auto-dismiss
  useEffect(() => {
    if (duration <= 0) return
    const timer = setTimeout(onDismiss, duration)
    return () => clearTimeout(timer)
  }, [duration, onDismiss])

  const styles = variantStyles[item.variant ?? 'default']
  const Icone = styles.icone

  return (
    <div
      role="status"
      className={cn(
        'pointer-events-auto flex gap-3 rounded-lg border p-4 shadow-lg',
        'animate-in slide-in-from-right-5 fade-in duration-200',
        styles.container,
      )}
    >
      <Icone className={cn('h-5 w-5 shrink-0 mt-0.5', styles.icon)} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{item.title}</div>
        {item.description && (
          <div className="text-xs mt-0.5 opacity-90 break-words">
            {item.description}
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        aria-label="Fechar"
        className={cn('shrink-0 rounded p-0.5 opacity-70 hover:opacity-100', styles.closer)}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

const variantStyles = {
  default: {
    icone: Info,
    container: 'border-border bg-surface text-surface-foreground',
    icon: 'text-primary',
    closer: 'hover:bg-muted',
  },
  success: {
    icone: CheckCircle2,
    container: 'border-success/30 bg-success/10 text-foreground',
    icon: 'text-success',
    closer: 'hover:bg-success/20',
  },
  destructive: {
    icone: AlertCircle,
    container: 'border-destructive/30 bg-destructive/10 text-foreground',
    icon: 'text-destructive',
    closer: 'hover:bg-destructive/20',
  },
}
