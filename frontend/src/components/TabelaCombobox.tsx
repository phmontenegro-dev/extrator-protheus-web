import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, Search, X } from 'lucide-react'
import { TabelaInfo } from '@/api/relatorioLivre'
import { cn } from '@/lib/utils'

/**
 * Combobox filtrável pra escolher uma tabela Protheus.
 *
 * O `<datalist>` nativo é inconsistente entre navegadores: no Chrome o filtro
 * só pega prefixo, no Firefox não filtra pelo meio da string, e com ~3600
 * tabelas a lista rolável fica impossível. Esse componente substitui tudo
 * isso com:
 *
 *   - filtro por substring (não só prefixo), em nome + descrição
 *   - navegação por teclado (↑ ↓ Enter Esc)
 *   - teto de 100 resultados por vez com aviso (3600 em 1 lista mataria render)
 *   - fecha ao clicar fora, selecionar ou apertar Esc
 *   - pré-seleciona o 1º resultado pra "digitou e Enter" funcionar sempre
 */
const LIMITE_RESULTADOS = 100

export function TabelaCombobox({
  tabelas,
  valor,                 // nome da tabela atualmente selecionada ("" se nenhuma)
  onEscolher,            // callback com o nome escolhido
  disabled,
}: {
  tabelas: TabelaInfo[]
  valor: string
  onEscolher: (nome: string) => void
  disabled?: boolean
}) {
  const [aberto, setAberto] = useState(false)
  const [filtro, setFiltro] = useState('')
  const [indiceAtivo, setIndiceAtivo] = useState(0)

  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const listaRef = useRef<HTMLDivElement | null>(null)

  const tabelaAtual = useMemo(
    () => tabelas.find((t) => t.nome === valor) ?? null,
    [tabelas, valor],
  )

  // Filtra tabelas por substring (case-insensitive) no nome OU descrição.
  const resultados = useMemo(() => {
    const q = filtro.trim().toUpperCase()
    if (!q) return tabelas.slice(0, LIMITE_RESULTADOS)
    const filtradas: TabelaInfo[] = []
    for (const t of tabelas) {
      const alvo = `${t.nome} ${(t.descricao ?? '').toUpperCase()}`
      if (alvo.includes(q)) {
        filtradas.push(t)
        if (filtradas.length >= LIMITE_RESULTADOS) break
      }
    }
    return filtradas
  }, [tabelas, filtro])

  const totalFiltrados = useMemo(() => {
    const q = filtro.trim().toUpperCase()
    if (!q) return tabelas.length
    let n = 0
    for (const t of tabelas) {
      const alvo = `${t.nome} ${(t.descricao ?? '').toUpperCase()}`
      if (alvo.includes(q)) n++
    }
    return n
  }, [tabelas, filtro])

  // Resetar índice quando o filtro muda.
  useEffect(() => {
    setIndiceAtivo(0)
  }, [filtro])

  // Scroll pro item ativo quando navega com teclado.
  useEffect(() => {
    if (!aberto || !listaRef.current) return
    const el = listaRef.current.querySelector<HTMLDivElement>(
      `[data-idx="${indiceAtivo}"]`,
    )
    el?.scrollIntoView({ block: 'nearest' })
  }, [indiceAtivo, aberto])

  // Fecha ao clicar fora.
  useEffect(() => {
    if (!aberto) return
    const onDoc = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setAberto(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [aberto])

  const abrir = () => {
    if (disabled) return
    setAberto(true)
    // Foca no input no próximo tick (depois que ele renderiza).
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const escolher = (t: TabelaInfo) => {
    onEscolher(t.nome)
    setFiltro('')
    setAberto(false)
  }

  const limpar = (e: React.MouseEvent) => {
    e.stopPropagation()
    onEscolher('')
    setFiltro('')
    setAberto(false)
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIndiceAtivo((i) => Math.min(i + 1, resultados.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setIndiceAtivo((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (resultados[indiceAtivo]) escolher(resultados[indiceAtivo])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setAberto(false)
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      {/* Gatilho: parece input + mostra a seleção */}
      <button
        type="button"
        onClick={aberto ? () => setAberto(false) : abrir}
        disabled={disabled}
        className={cn(
          'w-full flex items-center justify-between rounded-lg border bg-surface px-3 py-2 text-left',
          'outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          aberto ? 'border-primary ring-2 ring-ring' : 'border-border hover:border-primary/40',
        )}
      >
        <span className={cn('truncate font-mono text-sm', !tabelaAtual && 'text-muted-foreground font-sans')}>
          {tabelaAtual ? (
            <>
              <span className="font-semibold">{tabelaAtual.nome}</span>
              {tabelaAtual.descricao && (
                <span className="text-muted-foreground font-sans ml-2">
                  — {tabelaAtual.descricao}
                </span>
              )}
            </>
          ) : (
            'Selecionar tabela...'
          )}
        </span>
        <span className="flex items-center gap-1 shrink-0">
          {tabelaAtual && (
            <X
              onClick={limpar}
              className="h-4 w-4 text-muted-foreground hover:text-foreground"
              aria-label="Limpar"
            />
          )}
          <ChevronDown
            className={cn(
              'h-4 w-4 text-muted-foreground transition-transform',
              aberto && 'rotate-180',
            )}
          />
        </span>
      </button>

      {/* Painel do dropdown */}
      {aberto && (
        <div className="absolute z-20 mt-1 w-full rounded-lg border border-border bg-surface shadow-lg overflow-hidden">
          {/* Caixa de busca */}
          <div className="relative border-b border-border">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              ref={inputRef}
              value={filtro}
              onChange={(e) => setFiltro(e.target.value)}
              onKeyDown={onKey}
              placeholder="Digite para filtrar (ex.: SB1, cliente, fornecedor)"
              className="w-full pl-9 pr-3 py-2.5 bg-transparent text-sm outline-none"
              autoComplete="off"
              spellCheck={false}
            />
          </div>

          {/* Lista */}
          <div
            ref={listaRef}
            className="max-h-80 overflow-y-auto"
            role="listbox"
          >
            {resultados.length === 0 && (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                Nenhuma tabela encontrada para "{filtro}".
              </div>
            )}
            {resultados.map((t, i) => {
              const ativo = i === indiceAtivo
              const selecionado = t.nome === valor
              return (
                <div
                  key={t.nome}
                  data-idx={i}
                  role="option"
                  aria-selected={selecionado}
                  onMouseEnter={() => setIndiceAtivo(i)}
                  onMouseDown={(e) => {
                    // mousedown pra escolher antes do blur fechar
                    e.preventDefault()
                    escolher(t)
                  }}
                  className={cn(
                    'flex items-start gap-2 px-3 py-2 cursor-pointer text-sm',
                    ativo && 'bg-accent',
                  )}
                >
                  <Check
                    className={cn(
                      'h-4 w-4 mt-0.5 shrink-0',
                      selecionado ? 'text-primary' : 'text-transparent',
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="font-mono font-semibold">{t.nome}</div>
                    {t.descricao && (
                      <div className="text-xs text-muted-foreground truncate">
                        {t.descricao}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Rodapé com status */}
          <div className="px-3 py-1.5 text-[11px] text-muted-foreground border-t border-border bg-muted/40 flex justify-between">
            <span>
              {filtro
                ? `${resultados.length} de ${totalFiltrados} resultados`
                : `${tabelas.length} tabelas no total`}
            </span>
            {totalFiltrados > LIMITE_RESULTADOS && (
              <span>mostrando os primeiros {LIMITE_RESULTADOS} — refine o filtro</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
