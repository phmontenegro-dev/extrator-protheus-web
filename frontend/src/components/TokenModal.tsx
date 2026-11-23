import { useState } from 'react'
import { AlertTriangle, Check, Copy, X } from 'lucide-react'
import { Button } from './ui/button'

/**
 * Modal mostrado UMA VEZ após criar/regerar um agendamento.
 *
 * Avisa que o token em claro não vai ser mostrado de novo e oferece
 * botão "Copiar". Depois de fechar, o backend só guarda o hash — se o
 * usuário perder, precisa regenerar.
 */
export function TokenModal({
  tokenClaro,
  onFechar,
  acabouDeRegerar = false,
}: {
  tokenClaro: string
  onFechar: () => void
  acabouDeRegerar?: boolean
}) {
  const [copiado, setCopiado] = useState(false)

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(tokenClaro)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      // fallback: seleciona o input (navegadores antigos ou contextos inseguros)
      const el = document.getElementById('token-visivel') as HTMLInputElement | null
      el?.select()
      document.execCommand?.('copy')
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-lg rounded-lg border border-border bg-surface shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">
              {acabouDeRegerar ? 'Token regerado' : 'Token do agendamento'}
            </h2>
          </div>
          <button
            onClick={onFechar}
            className="rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Corpo */}
        <div className="px-5 py-4 space-y-4">
          <div className="rounded-md border border-primary/30 bg-primary/5 p-3 text-sm">
            <p className="font-medium text-foreground">
              Este token aparece <strong>uma única vez</strong>. Copie agora e guarde num
              lugar seguro.
            </p>
            <p className="text-muted-foreground mt-1.5 text-xs">
              O backend só guarda o hash. Se você perder, terá que gerar um token novo
              em "Regerar token" — e o script antigo para de funcionar.
              {acabouDeRegerar && (
                <>
                  <br />
                  <strong>O token anterior já foi invalidado.</strong>
                </>
              )}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Token
            </label>
            <div className="flex gap-2">
              <input
                id="token-visivel"
                type="text"
                value={tokenClaro}
                readOnly
                onClick={(e) => (e.target as HTMLInputElement).select()}
                className="flex-1 rounded-md border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:ring-2 focus:ring-ring"
              />
              <Button onClick={copiar} className="shrink-0">
                {copiado ? (
                  <>
                    <Check className="h-4 w-4" />
                    Copiado
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copiar
                  </>
                )}
              </Button>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Depois de fechar essa janela, baixe o script sincronizador na página do
            agendamento (botão <span className="font-medium text-foreground">Baixar script</span>) —
            o token fica embutido nele automaticamente.
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="outline" onClick={onFechar}>
            Já guardei
          </Button>
        </div>
      </div>
    </div>
  )
}

