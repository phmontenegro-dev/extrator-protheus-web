import { useState } from 'react'
import { Check, Copy, Download, FileCode2, X } from 'lucide-react'
import { ScriptGerado } from '@/api/agendamentos'
import { Button } from './ui/button'
import { cn } from '@/lib/utils'

/**
 * Modal que exibe o script gerado — botão de download + passo-a-passo
 * inline de instalação (que vem do backend, em Markdown simples).
 */
export function ScriptDownloadModal({
  script,
  onFechar,
}: {
  script: ScriptGerado
  onFechar: () => void
}) {
  const [aba, setAba] = useState<'baixar' | 'instrucoes'>('baixar')
  const [copiado, setCopiado] = useState(false)

  const baixar = () => {
    const blob = new Blob([script.conteudo], { type: 'text/x-python;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = script.nome_arquivo
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const copiarConteudo = async () => {
    try {
      await navigator.clipboard.writeText(script.conteudo)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    } catch {
      // ignora
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-3xl max-h-[90vh] flex flex-col rounded-lg border border-border bg-surface shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3 shrink-0">
          <div className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Script sincronizador</h2>
            <span className="text-xs font-mono text-muted-foreground">
              {script.nome_arquivo}
            </span>
          </div>
          <button
            onClick={onFechar}
            className="rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Abas */}
        <div className="flex border-b border-border shrink-0">
          <button
            onClick={() => setAba('baixar')}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              aba === 'baixar'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            Baixar
          </button>
          <button
            onClick={() => setAba('instrucoes')}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              aba === 'instrucoes'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            Instruções de instalação
          </button>
        </div>

        {/* Conteúdo scrollável */}
        <div className="flex-1 overflow-y-auto">
          {aba === 'baixar' && (
            <div className="p-5 space-y-4">
              <p className="text-sm text-muted-foreground">
                Baixe o arquivo e siga as instruções da outra aba pra instalar no PC.
                O token do agendamento já está embutido — não precisa configurar nada.
              </p>

              <div className="flex gap-2">
                <Button onClick={baixar} size="lg">
                  <Download className="h-4 w-4" />
                  Baixar {script.nome_arquivo}
                </Button>
                <Button variant="outline" onClick={copiarConteudo}>
                  {copiado ? (
                    <>
                      <Check className="h-4 w-4" />
                      Copiado
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      Copiar conteúdo
                    </>
                  )}
                </Button>
              </div>

              <details className="rounded-md border border-border">
                <summary className="cursor-pointer px-3 py-2 text-xs text-muted-foreground hover:text-foreground select-none">
                  Preview do conteúdo
                </summary>
                <pre className="px-3 py-2 text-xs font-mono bg-muted overflow-auto max-h-[300px]">
                  {script.conteudo}
                </pre>
              </details>
            </div>
          )}

          {aba === 'instrucoes' && (
            <div className="p-5">
              {/* Instruções vêm em Markdown do backend. Rendermos de forma simples:
                  parsing mínimo pra headings, código inline, bloco de código e listas.
                  Pra dependência zero. Se quisermos algo mais sofisticado depois,
                  trocamos por react-markdown. */}
              <MarkdownSimples texto={script.instrucoes} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3 shrink-0">
          <Button variant="outline" onClick={onFechar}>
            Fechar
          </Button>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Mini-renderer de Markdown (sem dependências externas)
// =============================================================================

/**
 * Renderer simples e escapado. Cobre:
 *   - # / ## / ### headings
 *   - ```lang ... ``` blocos de código
 *   - `código inline`
 *   - **negrito**
 *   - listas numeradas (1. 2. 3.) e com - ou *
 *   - parágrafos separados por linha em branco
 *
 * Suficiente pras instruções do backend. Não usamos dangerouslySetInnerHTML.
 */
function MarkdownSimples({ texto }: { texto: string }) {
  const blocos = splitBlocos(texto)
  return (
    <div className="prose-sm max-w-none space-y-4 text-sm leading-relaxed">
      {blocos.map((b, i) => (
        <RenderBloco key={i} bloco={b} />
      ))}
    </div>
  )
}

type Bloco =
  | { tipo: 'h1' | 'h2' | 'h3'; texto: string }
  | { tipo: 'code'; lang: string; texto: string }
  | { tipo: 'lista-num'; itens: string[] }
  | { tipo: 'lista-bul'; itens: string[] }
  | { tipo: 'paragrafo'; texto: string }

function splitBlocos(src: string): Bloco[] {
  const linhas = src.replace(/\r\n/g, '\n').split('\n')
  const out: Bloco[] = []
  let i = 0
  while (i < linhas.length) {
    const l = linhas[i]

    // bloco de código ```
    if (l.startsWith('```')) {
      const lang = l.slice(3).trim()
      const buf: string[] = []
      i++
      while (i < linhas.length && !linhas[i].startsWith('```')) {
        buf.push(linhas[i])
        i++
      }
      i++ // pula a ``` de fechamento
      out.push({ tipo: 'code', lang, texto: buf.join('\n') })
      continue
    }

    // headings
    const h3 = l.match(/^###\s+(.*)$/)
    if (h3) { out.push({ tipo: 'h3', texto: h3[1] }); i++; continue }
    const h2 = l.match(/^##\s+(.*)$/)
    if (h2) { out.push({ tipo: 'h2', texto: h2[1] }); i++; continue }
    const h1 = l.match(/^#\s+(.*)$/)
    if (h1) { out.push({ tipo: 'h1', texto: h1[1] }); i++; continue }

    // lista numerada
    if (/^\d+\.\s+/.test(l)) {
      const itens: string[] = []
      while (i < linhas.length && /^\d+\.\s+/.test(linhas[i])) {
        itens.push(linhas[i].replace(/^\d+\.\s+/, ''))
        i++
      }
      out.push({ tipo: 'lista-num', itens })
      continue
    }

    // lista com -
    if (/^[-*]\s+/.test(l)) {
      const itens: string[] = []
      while (i < linhas.length && /^[-*]\s+/.test(linhas[i])) {
        itens.push(linhas[i].replace(/^[-*]\s+/, ''))
        i++
      }
      out.push({ tipo: 'lista-bul', itens })
      continue
    }

    // linha em branco — separador
    if (l.trim() === '') { i++; continue }

    // parágrafo (junta linhas consecutivas até achar vazio ou um marcador)
    const buf: string[] = [l]
    i++
    while (
      i < linhas.length &&
      linhas[i].trim() !== '' &&
      !linhas[i].startsWith('```') &&
      !/^#{1,3}\s+/.test(linhas[i]) &&
      !/^\d+\.\s+/.test(linhas[i]) &&
      !/^[-*]\s+/.test(linhas[i])
    ) {
      buf.push(linhas[i])
      i++
    }
    out.push({ tipo: 'paragrafo', texto: buf.join(' ') })
  }
  return out
}

function RenderBloco({ bloco }: { bloco: Bloco }) {
  switch (bloco.tipo) {
    case 'h1':
      return <h1 className="text-xl font-bold mt-4 mb-2">{formatInline(bloco.texto)}</h1>
    case 'h2':
      return <h2 className="text-lg font-semibold mt-4 mb-2">{formatInline(bloco.texto)}</h2>
    case 'h3':
      return <h3 className="text-base font-semibold mt-3 mb-1.5">{formatInline(bloco.texto)}</h3>
    case 'code':
      return (
        <pre className="px-3 py-2 rounded-md bg-muted font-mono text-xs overflow-x-auto">
          {bloco.lang && (
            <div className="text-[10px] text-muted-foreground mb-1 uppercase">{bloco.lang}</div>
          )}
          {bloco.texto}
        </pre>
      )
    case 'lista-num':
      return (
        <ol className="list-decimal pl-6 space-y-1">
          {bloco.itens.map((it, i) => <li key={i}>{formatInline(it)}</li>)}
        </ol>
      )
    case 'lista-bul':
      return (
        <ul className="list-disc pl-6 space-y-1">
          {bloco.itens.map((it, i) => <li key={i}>{formatInline(it)}</li>)}
        </ul>
      )
    case 'paragrafo':
      return <p>{formatInline(bloco.texto)}</p>
  }
}

/** Renderiza `código` inline e **negrito** dentro de uma string. */
function formatInline(src: string): React.ReactNode[] {
  const out: React.ReactNode[] = []
  // split por `codigo` e depois por **negrito**
  const codeRe = /`([^`]+)`/g
  let lastIdx = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = codeRe.exec(src)) !== null) {
    if (m.index > lastIdx) {
      out.push(...formatNegrito(src.slice(lastIdx, m.index), k))
      k += 10
    }
    out.push(
      <code key={`c-${k++}`} className="rounded bg-muted px-1 py-0.5 text-[0.85em] font-mono">
        {m[1]}
      </code>,
    )
    lastIdx = m.index + m[0].length
  }
  if (lastIdx < src.length) {
    out.push(...formatNegrito(src.slice(lastIdx), k))
  }
  return out
}

function formatNegrito(src: string, keyBase: number): React.ReactNode[] {
  const re = /\*\*([^*]+)\*\*/g
  const out: React.ReactNode[] = []
  let lastIdx = 0
  let m: RegExpExecArray | null
  let k = keyBase
  while ((m = re.exec(src)) !== null) {
    if (m.index > lastIdx) out.push(<span key={`t-${k++}`}>{src.slice(lastIdx, m.index)}</span>)
    out.push(<strong key={`b-${k++}`}>{m[1]}</strong>)
    lastIdx = m.index + m[0].length
  }
  if (lastIdx < src.length) out.push(<span key={`t-${k++}`}>{src.slice(lastIdx)}</span>)
  return out
}
