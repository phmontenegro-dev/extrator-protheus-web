import { cn } from '@/lib/utils'

/**
 * Logo da aplicação. A imagem em /public/logo.png é a silhueta PB — como
 * fica preta em cima de fundo escuro no dark mode, invertemos com
 * `dark:invert` (vira branco).
 */
export function Logo({
  className,
  showText = true,
}: {
  className?: string
  showText?: boolean
}) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <img
        src="/logo.png"
        alt="Extrator Protheus"
        className="h-9 w-9 object-contain dark:invert"
      />
      {showText && (
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold">Extrator Protheus</span>
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Technocoat
          </span>
        </div>
      )}
    </div>
  )
}
