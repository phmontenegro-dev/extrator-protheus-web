import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ColunaInfo,
  FiltroCampo,
  OPERADORES_POR_TIPO,
  Operador,
  ROTULO_OPERADOR,
  TabelaInfo,
  TipoLogico,
  listarColunas,
  listarTabelas,
} from '../../api/relatorioLivre'
import { criarJobLivre } from '../../api/jobs'
import { mensagemErro } from '../../api/client'
import { useToast } from '../../lib/toast'
import { TabelaCombobox } from '../../components/TabelaCombobox'

/**
 * Formulário do Relatório Livre.
 *
 * Fluxo:
 *   1. Carrega a lista de tabelas Protheus (pode demorar — consulta ALL_TABLES)
 *   2. Usuário escolhe uma tabela via TabelaCombobox (filtra por substring)
 *   3. Ao escolher, buscamos as colunas (ALL_TAB_COLUMNS, com tipo lógico)
 *   4. Usuário marca as colunas + escolhe campo_data (opcional)
 *   5. (Etapa 12) Adiciona filtros dinâmicos — um ou vários, por coluna,
 *      com operador adequado ao tipo
 *   6. Preenche datas (se campo_data informado) e max_linhas (opcional)
 *   7. Extrair em background → aparece em "Meus jobs"
 */

// ---- Linha de filtro dinâmico no state ----
// id local pra React key; o backend recebe {coluna, operador, valor}.
type FiltroLinha = {
  id: number
  coluna: string     // "" = ainda não escolhida
  operador: Operador | ''
  // Mantemos valor como string(s) na UI — convertido na hora de submeter.
  valor: string
  valor2: string     // usado apenas quando operador é "entre" / "data_entre"
}

let _contadorFiltros = 0
function novaLinha(): FiltroLinha {
  _contadorFiltros += 1
  return { id: _contadorFiltros, coluna: '', operador: '', valor: '', valor2: '' }
}

export default function FormLivre() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [tabelas, setTabelas] = useState<TabelaInfo[]>([])
  const [tabelasCarregando, setTabelasCarregando] = useState(true)
  const [erroGeral, setErroGeral] = useState<string | null>(null)

  // Seleção do usuário. tabelaNome é o nome da tabela selecionada ("" = nenhuma).
  const [tabelaNome, setTabelaNome] = useState('')
  const [colunasDisponiveis, setColunasDisponiveis] = useState<ColunaInfo[]>([])
  const [colunasSelecionadas, setColunasSelecionadas] = useState<Set<string>>(new Set())
  const [carregandoColunas, setCarregandoColunas] = useState(false)
  const [erroColunas, setErroColunas] = useState<string | null>(null)

  const [campoData, setCampoData] = useState<string>('')    // "" = sem filtro de data
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')
  const [maxLinhas, setMaxLinhas] = useState('')

  // Etapa 12: filtros dinâmicos.
  const [filtrosExtra, setFiltrosExtra] = useState<FiltroLinha[]>([])

  const [extraindo, setExtraindo] = useState(false)
  const [erroExtracao, setErroExtracao] = useState<string | null>(null)

  // Bootstrap: lista de tabelas.
  useEffect(() => {
    let ativo = true
    listarTabelas()
      .then((ts) => {
        if (ativo) setTabelas(ts)
      })
      .catch((e) => {
        if (ativo) setErroGeral(mensagemErro(e, 'Não foi possível carregar as tabelas.'))
      })
      .finally(() => {
        if (ativo) setTabelasCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  // Lookup rápido de metadata (descrição + campo_data sugerido).
  const mapaTabelas = useMemo(() => {
    const m = new Map<string, TabelaInfo>()
    tabelas.forEach((t) => m.set(t.nome, t))
    return m
  }, [tabelas])

  const tabelaSelecionada = tabelaNome ? mapaTabelas.get(tabelaNome) ?? null : null

  // Index rápido coluna -> tipo_logico, para a UI dos filtros extras.
  const tipoPorColuna = useMemo(() => {
    const m = new Map<string, TipoLogico>()
    colunasDisponiveis.forEach((c) => m.set(c.nome, c.tipo_logico))
    return m
  }, [colunasDisponiveis])

  // Lista só os nomes — usado em várias listas <select>.
  const nomesColunas = useMemo(
    () => colunasDisponiveis.map((c) => c.nome),
    [colunasDisponiveis],
  )

  // Ao trocar de tabela (válida), busca as colunas e aplica a sugestão de
  // campo_data se a tabela estiver no TABELAS_CONHECIDAS.
  useEffect(() => {
    if (!tabelaSelecionada) {
      setColunasDisponiveis([])
      setColunasSelecionadas(new Set())
      setCampoData('')
      setErroColunas(null)
      setFiltrosExtra([])
      return
    }

    let ativo = true
    setCarregandoColunas(true)
    setErroColunas(null)
    setColunasSelecionadas(new Set())
    setFiltrosExtra([]) // trocou de tabela → zera filtros extras

    listarColunas(tabelaSelecionada.nome)
      .then((r) => {
        if (!ativo) return
        setColunasDisponiveis(r.colunas)
        // Pré-seleciona o campo de data se sugerido E se existe na tabela.
        const sugestao = tabelaSelecionada.campo_data_sugerido
        const nomes = r.colunas.map((c) => c.nome)
        if (sugestao && nomes.includes(sugestao)) {
          setCampoData(sugestao)
        } else {
          setCampoData('')
        }
      })
      .catch((e) => {
        if (ativo) setErroColunas(mensagemErro(e, 'Não foi possível carregar as colunas.'))
      })
      .finally(() => {
        if (ativo) setCarregandoColunas(false)
      })

    return () => {
      ativo = false
    }
  }, [tabelaSelecionada])

  const toggleColuna = (col: string) => {
    const nova = new Set(colunasSelecionadas)
    if (nova.has(col)) nova.delete(col)
    else nova.add(col)
    setColunasSelecionadas(nova)
  }

  const marcarTodas = () => setColunasSelecionadas(new Set(nomesColunas))
  const limparSelecao = () => setColunasSelecionadas(new Set())

  // ---- Helpers para filtros_extra ----

  const adicionarFiltro = () => setFiltrosExtra((xs) => [...xs, novaLinha()])
  const removerFiltro = (id: number) =>
    setFiltrosExtra((xs) => xs.filter((x) => x.id !== id))
  const atualizarFiltro = (id: number, patch: Partial<FiltroLinha>) =>
    setFiltrosExtra((xs) =>
      xs.map((x) => {
        if (x.id !== id) return x
        const novo = { ...x, ...patch }
        // Se trocou a coluna, o operador antigo pode não servir pro novo tipo.
        if ('coluna' in patch) {
          const tipo = novo.coluna ? tipoPorColuna.get(novo.coluna) : undefined
          if (!tipo || !OPERADORES_POR_TIPO[tipo].includes(novo.operador as Operador)) {
            novo.operador = ''
            novo.valor = ''
            novo.valor2 = ''
          }
        }
        // Se trocou o operador, limpa os valores — o tipo de input muda.
        if ('operador' in patch) {
          novo.valor = ''
          novo.valor2 = ''
        }
        return novo
      }),
    )

  /** Converte as linhas da UI em payload do backend; retorna erro se inválido. */
  const montarFiltrosExtra = (): { ok: true; data: FiltroCampo[] } | { ok: false; erro: string } => {
    const out: FiltroCampo[] = []
    for (const [i, l] of filtrosExtra.entries()) {
      const posicao = `Filtro #${i + 1}`
      if (!l.coluna) return { ok: false, erro: `${posicao}: escolha uma coluna.` }
      if (!l.operador) return { ok: false, erro: `${posicao}: escolha um operador.` }
      const tipo = tipoPorColuna.get(l.coluna)
      if (!tipo) return { ok: false, erro: `${posicao}: coluna inválida.` }

      // Operadores sem valor.
      if (l.operador === 'is_null' || l.operador === 'nao_is_null') {
        out.push({ coluna: l.coluna, operador: l.operador, valor: null })
        continue
      }

      // em_lista: aceita vírgula OU quebra de linha; remove vazios.
      if (l.operador === 'em_lista') {
        const itens = l.valor
          .split(/[\n,;]/)
          .map((s) => s.trim())
          .filter((s) => s.length > 0)
        if (itens.length === 0) {
          return { ok: false, erro: `${posicao}: informe pelo menos um valor (separe por vírgula).` }
        }
        out.push({ coluna: l.coluna, operador: l.operador, valor: itens })
        continue
      }

      // ultimos_n_dias: inteiro ≥ 0
      if (l.operador === 'ultimos_n_dias') {
        const n = Number(l.valor)
        if (!Number.isInteger(n) || n < 0) {
          return { ok: false, erro: `${posicao}: informe um nº inteiro de dias (ex: 7).` }
        }
        out.push({ coluna: l.coluna, operador: l.operador, valor: n })
        continue
      }

      // entre / data_entre: dois valores
      if (l.operador === 'entre' || l.operador === 'data_entre') {
        if (!l.valor || !l.valor2) {
          return { ok: false, erro: `${posicao}: informe os dois valores (mín. e máx.).` }
        }
        if (l.operador === 'entre') {
          const a = Number(l.valor), b = Number(l.valor2)
          if (Number.isNaN(a) || Number.isNaN(b)) {
            return { ok: false, erro: `${posicao}: valores numéricos inválidos.` }
          }
          out.push({ coluna: l.coluna, operador: l.operador, valor: [a, b] })
        } else {
          if (l.valor > l.valor2) {
            return { ok: false, erro: `${posicao}: data inicial maior que a final.` }
          }
          out.push({ coluna: l.coluna, operador: l.operador, valor: [l.valor, l.valor2] })
        }
        continue
      }

      // Caso simples: valor único.
      if (l.valor === '') {
        return { ok: false, erro: `${posicao}: informe um valor.` }
      }
      if (tipo === 'numero') {
        const n = Number(l.valor)
        if (Number.isNaN(n)) {
          return { ok: false, erro: `${posicao}: "${l.valor}" não é um número.` }
        }
        out.push({ coluna: l.coluna, operador: l.operador, valor: n })
      } else {
        out.push({ coluna: l.coluna, operador: l.operador, valor: l.valor })
      }
    }
    return { ok: true, data: out }
  }

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErroExtracao(null)

    if (!tabelaSelecionada) {
      setErroExtracao('Escolha uma tabela válida da lista.')
      return
    }
    if (colunasSelecionadas.size === 0) {
      setErroExtracao('Selecione pelo menos uma coluna.')
      return
    }

    const temCampoData = campoData.trim() !== ''
    if (temCampoData) {
      if (!dataInicio || !dataFim) {
        setErroExtracao('Informe as duas datas quando o campo de data estiver definido.')
        return
      }
      if (dataInicio > dataFim) {
        setErroExtracao('Data inicial não pode ser maior que data final.')
        return
      }
    } else if (filtrosExtra.length === 0) {
      // Só pede confirmação se NÃO tem filtro extra também — se tem, já está
      // filtrado por outra coisa, não vale a pena interromper.
      const prosseguir = window.confirm(
        'Você escolheu NÃO filtrar por data nem adicionar outros filtros. A extração pode retornar milhões de linhas e ' +
        'demorar bastante. Deseja continuar?'
      )
      if (!prosseguir) return
    }

    const max = maxLinhas.trim()
    let maxNum: number | null = null
    if (max) {
      const n = Number(max)
      if (!Number.isInteger(n) || n <= 0) {
        setErroExtracao('Máximo de linhas deve ser um inteiro positivo.')
        return
      }
      maxNum = n
    }

    const resFiltros = montarFiltrosExtra()
    if (!resFiltros.ok) {
      setErroExtracao(resFiltros.erro)
      return
    }

    setExtraindo(true)
    try {
      const r = await criarJobLivre({
        tabela: tabelaSelecionada.nome,
        colunas: Array.from(colunasSelecionadas),
        campo_data: temCampoData ? campoData : null,
        data_inicio: temCampoData ? dataInicio : null,
        data_fim: temCampoData ? dataFim : null,
        max_linhas: maxNum,
        filtros_extra: resFiltros.data,
      })
      toast({
        title: 'Job criado',
        description: 'Acompanhe o progresso em "Meus jobs".',
        variant: 'success',
      })
      navigate(`/jobs?focus=${encodeURIComponent(r.job_id)}`)
    } catch (e) {
      const msg = mensagemErro(e, 'Falha ao enviar o job.')
      setErroExtracao(msg)
      toast({ title: 'Não foi possível enviar', description: msg, variant: 'destructive' })
      setExtraindo(false)
    }
  }

  // ---- Render ----

  if (tabelasCarregando) {
    return <p className="text-muted-foreground">Carregando lista de tabelas...</p>
  }

  if (erroGeral) {
    return (
      <div className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3">
        {erroGeral}
      </div>
    )
  }

  return (
    <form onSubmit={submeter} className="space-y-6">
      {/* 1) Tabela */}
      <div>
        <label htmlFor="tabela" className="block text-sm font-medium mb-1">
          Tabela
        </label>
        <TabelaCombobox
          tabelas={tabelas}
          valor={tabelaNome}
          onEscolher={setTabelaNome}
          disabled={extraindo}
        />
        <p className="text-xs text-muted-foreground mt-1">
          {tabelas.length} tabelas disponíveis — digite para filtrar por nome ou descrição.
        </p>
      </div>

      {/* 2) Colunas */}
      {tabelaSelecionada && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium">Colunas a extrair</label>
            {colunasDisponiveis.length > 0 && (
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={marcarTodas}
                  className="px-2 py-1 rounded border border-border"
                >
                  Marcar todas
                </button>
                <button
                  type="button"
                  onClick={limparSelecao}
                  className="px-2 py-1 rounded border border-border"
                >
                  Limpar
                </button>
              </div>
            )}
          </div>

          {carregandoColunas && (
            <p className="text-sm text-muted-foreground">Carregando colunas...</p>
          )}
          {erroColunas && (
            <div className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3">
              {erroColunas}
            </div>
          )}

          {!carregandoColunas && !erroColunas && (
            <>
              <div className="border border-border rounded-lg p-3 max-h-72 overflow-y-auto grid grid-cols-2 md:grid-cols-3 gap-y-1 gap-x-3">
                {colunasDisponiveis.map((c) => (
                  <label key={c.nome} className="flex items-center gap-2 text-xs font-mono">
                    <input
                      type="checkbox"
                      checked={colunasSelecionadas.has(c.nome)}
                      onChange={() => toggleColuna(c.nome)}
                      className="rounded"
                    />
                    {c.nome}
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {colunasSelecionadas.size} selecionadas / {colunasDisponiveis.length} disponíveis.
                Campos binários (BLOB, LONG, RAW) são ocultados automaticamente.
              </p>
            </>
          )}
        </div>
      )}

      {/* 3) Campo de data + período */}
      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div className="space-y-3">
          <div>
            <label htmlFor="campo_data" className="block text-sm font-medium mb-1">
              Campo de data
            </label>
            <select
              id="campo_data"
              value={campoData}
              onChange={(e) => setCampoData(e.target.value)}
              disabled={extraindo}
              className="w-full md:w-80 rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm"
            >
              <option value="">(sem filtro de data)</option>
              {nomesColunas.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground mt-1">
              Escolha a coluna que será usada no BETWEEN, ou deixe "(sem filtro de data)".
            </p>
          </div>

          {campoData && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="di" className="block text-sm font-medium mb-1">Data inicial</label>
                <input
                  id="di"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="df" className="block text-sm font-medium mb-1">Data final</label>
                <input
                  id="df"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4) Filtros dinâmicos (Etapa 12) */}
      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium">
              Filtros adicionais{' '}
              <span className="text-muted-foreground text-xs">(opcional)</span>
            </label>
            <button
              type="button"
              onClick={adicionarFiltro}
              disabled={extraindo}
              className="px-3 py-1 rounded border border-border text-xs"
            >
              + Adicionar filtro
            </button>
          </div>

          {filtrosExtra.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Sem filtros adicionais — clique em "+ Adicionar filtro" pra restringir por valor,
              lista, faixa, data etc.
            </p>
          )}

          <div className="space-y-2">
            {filtrosExtra.map((linha) => (
              <LinhaFiltro
                key={linha.id}
                linha={linha}
                colunas={colunasDisponiveis}
                tipoPorColuna={tipoPorColuna}
                disabled={extraindo}
                onChange={(patch) => atualizarFiltro(linha.id, patch)}
                onRemover={() => removerFiltro(linha.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* 5) Max linhas */}
      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div>
          <label htmlFor="max_linhas" className="block text-sm font-medium mb-1">
            Máximo de linhas <span className="text-muted-foreground text-xs">(opcional)</span>
          </label>
          <input
            id="max_linhas"
            type="number"
            min="1"
            step="1"
            value={maxLinhas}
            onChange={(e) => setMaxLinhas(e.target.value)}
            disabled={extraindo}
            placeholder="Sem limite"
            className="w-full md:w-48 rounded-lg border border-border bg-surface px-3 py-2"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Aplica <span className="font-mono">ROWNUM &lt;= N</span>. Útil para teste rápido.
          </p>
        </div>
      )}

      {erroExtracao && (
        <div
          role="alert"
          className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3"
        >
          {erroExtracao}
        </div>
      )}

      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div>
          <button
            type="submit"
            disabled={extraindo || colunasSelecionadas.size === 0}
            className="w-full md:w-auto px-6 bg-primary text-primary-foreground rounded-lg py-2 font-medium disabled:opacity-50"
          >
            {extraindo ? 'Enviando...' : 'Extrair em background'}
          </button>
          <p className="text-xs text-muted-foreground mt-2">
            A extração roda em background — você pode fechar a aba que o CSV estará esperando em{' '}
            <button type="button" className="underline" onClick={() => navigate('/jobs')}>
              Meus jobs
            </button>.
          </p>
        </div>
      )}
    </form>
  )
}

// ---------------------------------------------------------------------------
// LinhaFiltro — um filtro dinâmico individual
// ---------------------------------------------------------------------------

type LinhaFiltroProps = {
  linha: FiltroLinha
  colunas: ColunaInfo[]
  tipoPorColuna: Map<string, TipoLogico>
  disabled: boolean
  onChange: (patch: Partial<FiltroLinha>) => void
  onRemover: () => void
}

function LinhaFiltro({
  linha, colunas, tipoPorColuna, disabled, onChange, onRemover,
}: LinhaFiltroProps) {
  const tipo = linha.coluna ? tipoPorColuna.get(linha.coluna) : undefined
  const operadoresDisponiveis = tipo ? OPERADORES_POR_TIPO[tipo] : []

  // Decide o tipo de input baseado em (tipo, operador).
  const tipoInput = useMemo<'texto' | 'numero' | 'data' | 'nenhum' | 'em_lista' | 'inteiro'>(() => {
    if (!linha.operador) return 'texto'
    if (linha.operador === 'is_null' || linha.operador === 'nao_is_null') return 'nenhum'
    if (linha.operador === 'em_lista') return 'em_lista'
    if (linha.operador === 'ultimos_n_dias') return 'inteiro'
    if (tipo === 'numero') return 'numero'
    if (tipo === 'data') return 'data'
    return 'texto'
  }, [tipo, linha.operador])

  const precisaDoisValores =
    linha.operador === 'entre' || linha.operador === 'data_entre'

  return (
    <div className="border border-border rounded-lg p-3 space-y-2 bg-surface/50">
      <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2">
        {/* Coluna */}
        <select
          value={linha.coluna}
          onChange={(e) => onChange({ coluna: e.target.value })}
          disabled={disabled}
          className="rounded-lg border border-border bg-surface px-2 py-1.5 font-mono text-sm"
        >
          <option value="">— coluna —</option>
          {colunas.map((c) => (
            <option key={c.nome} value={c.nome}>
              {c.nome} ({c.tipo_logico})
            </option>
          ))}
        </select>

        {/* Operador */}
        <select
          value={linha.operador}
          onChange={(e) => onChange({ operador: e.target.value as Operador })}
          disabled={disabled || !linha.coluna}
          className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm"
        >
          <option value="">— operador —</option>
          {operadoresDisponiveis.map((op) => (
            <option key={op} value={op}>
              {ROTULO_OPERADOR[op]}
            </option>
          ))}
        </select>

        {/* Remover */}
        <button
          type="button"
          onClick={onRemover}
          disabled={disabled}
          aria-label="Remover filtro"
          className="px-3 py-1.5 rounded-lg border border-border text-xs"
        >
          Remover
        </button>
      </div>

      {/* Valor(es) */}
      {tipoInput !== 'nenhum' && linha.operador && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {tipoInput === 'em_lista' ? (
            <textarea
              value={linha.valor}
              onChange={(e) => onChange({ valor: e.target.value })}
              disabled={disabled}
              placeholder="Valores separados por vírgula ou um por linha"
              rows={2}
              className="md:col-span-2 rounded-lg border border-border bg-surface px-2 py-1.5 text-sm font-mono"
            />
          ) : (
            <input
              type={
                tipoInput === 'data' ? 'date'
                  : tipoInput === 'numero' || tipoInput === 'inteiro' ? 'number'
                  : 'text'
              }
              step={tipoInput === 'inteiro' ? '1' : undefined}
              min={tipoInput === 'inteiro' ? '0' : undefined}
              value={linha.valor}
              onChange={(e) => onChange({ valor: e.target.value })}
              disabled={disabled}
              placeholder={precisaDoisValores ? 'mínimo' : undefined}
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm"
            />
          )}

          {precisaDoisValores && (
            <input
              type={tipoInput === 'data' ? 'date' : 'number'}
              value={linha.valor2}
              onChange={(e) => onChange({ valor2: e.target.value })}
              disabled={disabled}
              placeholder="máximo"
              className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm"
            />
          )}
        </div>
      )}
    </div>
  )
}
