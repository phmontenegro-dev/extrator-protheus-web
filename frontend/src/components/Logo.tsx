import { cn } from '@/lib/utils'

/**
 * Logo da Technocoat. Imagem em /public/logo.png — a Vite serve estático
 * de public/ na raiz. Se um dia virar SVG, troca o caminho aqui.
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
        alt="Technocoat"
        className="h-8 w-8 object-contain"
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
